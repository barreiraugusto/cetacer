"""Vistas del panel de administración de CETACER."""
from datetime import date, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from contenido.models import Pagina
from cuentas.models import DESCRIPCION_ROLES, JERARQUIA, Usuario
from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso

from .accesos import (
    GESTION,
    SOLO_DIRECCION,
    requiere_panel,
)
from .forms import (
    CategoriaForm,
    ConfiguracionForm,
    CursoForm,
    EnlaceFormSet,
    FechaForm,
    ImagenPortadaFormSet,
    PaginaForm,
    UsuarioForm,
)


def _volver(request, por_defecto):
    """Vuelve a `next` si es una dirección propia; si no, al destino por defecto."""
    destino = request.POST.get("next")
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(destino)
    return redirect(por_defecto)


# --- Tablero ---------------------------------------------------------------

@requiere_panel
def inicio(request):
    """Tablero de entrada: las próximas fechas y su estado, en un vistazo."""
    proximas = Comision.objects.select_related("curso", "curso__categoria").filter(
        fecha_inicio__gte=date.today()
    )
    return render(request, "panel/inicio.html", {
        "seccion": "inicio",
        "indicadores": {
            "publicadas": proximas.filter(visible=True).count(),
            "completas": proximas.filter(visible=True, completa=True).count(),
            "ocultas": proximas.filter(visible=False).count(),
        },
        "proximas": proximas.order_by("fecha_inicio", "hora_inicio")[:10],
    })


@requiere_panel
def agenda(request):
    """Calendario mensual de fechas."""
    hoy = date.today()
    try:
        anio = int(request.GET.get("anio", hoy.year))
        mes = int(request.GET.get("mes", hoy.month))
        primero = date(anio, mes, 1)
    except (ValueError, TypeError):
        primero = date(hoy.year, hoy.month, 1)

    siguiente = date(primero.year + (primero.month == 12), (primero.month % 12) + 1, 1)
    anterior_mes = primero.month - 1 or 12
    anterior = date(primero.year - (primero.month == 1), anterior_mes, 1)

    fechas = Comision.objects.select_related("curso").filter(
        fecha_inicio__gte=primero, fecha_inicio__lt=siguiente
    ).order_by("fecha_inicio", "hora_inicio")

    por_dia = {}
    for fecha in fechas:
        por_dia.setdefault(fecha.fecha_inicio.day, []).append(fecha)

    # Grilla de 6 semanas arrancando en lunes.
    desplazamiento = primero.weekday()
    celdas = []
    for indice in range(42):
        dia = primero + timedelta(days=indice - desplazamiento)
        celdas.append({
            "fecha": dia,
            "del_mes": dia.month == primero.month,
            "es_hoy": dia == hoy,
            "comisiones": por_dia.get(dia.day, []) if dia.month == primero.month else [],
        })

    return render(request, "panel/agenda.html", {
        "seccion": "agenda",
        "mes_actual": primero,
        "mes_anterior": anterior,
        "mes_siguiente": siguiente,
        "celdas": celdas,
        "total": fechas.count(),
    })


# --- Catálogo --------------------------------------------------------------

@requiere_panel
def cursos_lista(request):
    consulta = Curso.objects.select_related("categoria").annotate(
        total_comisiones=Count("comisiones", distinct=True)
    )
    busqueda = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "")
    if busqueda:
        consulta = consulta.filter(Q(nombre__icontains=busqueda) | Q(requisitos__icontains=busqueda))
    if categoria:
        consulta = consulta.filter(categoria_id=categoria)
    return render(request, "panel/cursos.html", {
        "seccion": "cursos",
        "cursos": consulta,
        "categorias": Categoria.objects.all(),
        "q": busqueda,
        "categoria_sel": categoria,
    })


@GESTION
def curso_editar(request, pk=None):
    curso = get_object_or_404(Curso, pk=pk) if pk else None
    if request.method == "POST":
        formulario = CursoForm(request.POST, instance=curso)
        if formulario.is_valid():
            guardado = formulario.save()
            messages.success(
                request,
                f"Curso «{guardado.nombre}» {'actualizado' if pk else 'creado'}.",
            )
            return redirect("panel:cursos")
        messages.error(request, "Revisá los campos marcados en rojo.")
    else:
        formulario = CursoForm(instance=curso)
    return render(request, "panel/curso_form.html", {
        "seccion": "cursos",
        "form": formulario,
        "curso": curso,
    })


@GESTION
def curso_eliminar(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    if request.method != "POST":
        return redirect("panel:curso_editar", pk=pk)
    if curso.comisiones.exists():
        messages.error(
            request,
            "Ese curso tiene fechas cargadas. Borralas primero, o desactivá el curso "
            "para que deje de verse en la web.",
        )
        return redirect("panel:curso_editar", pk=pk)
    nombre = curso.nombre
    curso.delete()
    messages.success(request, f"Curso «{nombre}» eliminado.")
    return redirect("panel:cursos")


@requiere_panel
def categorias_lista(request):
    return render(request, "panel/categorias.html", {
        "seccion": "cursos",
        "categorias": Categoria.objects.annotate(total=Count("cursos")),
    })


@GESTION
def categoria_editar(request, pk=None):
    categoria = get_object_or_404(Categoria, pk=pk) if pk else None
    if request.method == "POST":
        formulario = CategoriaForm(request.POST, request.FILES, instance=categoria)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, "Categoría guardada.")
            return redirect("panel:categorias")
    else:
        formulario = CategoriaForm(instance=categoria)
    return render(request, "panel/categoria_form.html", {
        "seccion": "cursos",
        "form": formulario,
        "categoria": categoria,
    })


@GESTION
def paginas_lista(request):
    return render(request, "panel/paginas.html", {
        "seccion": "paginas",
        "paginas_cargadas": Pagina.objects.prefetch_related("enlaces"),
    })


@GESTION
def pagina_editar(request, pk=None):
    """La página y sus enlaces se guardan juntos o no se guarda nada."""
    pagina = get_object_or_404(Pagina, pk=pk) if pk else None
    if request.method == "POST":
        formulario = PaginaForm(request.POST, instance=pagina)
        enlaces = EnlaceFormSet(request.POST, request.FILES, instance=pagina)
        if formulario.is_valid() and enlaces.is_valid():
            with transaction.atomic():
                guardada = formulario.save()
                enlaces.instance = guardada
                enlaces.save()
            messages.success(request, f"Página «{guardada.titulo}» guardada.")
            return redirect("panel:paginas")
        messages.error(
            request,
            "Revisá los campos marcados en rojo."
            if not formulario.is_valid()
            else "Revisá los enlaces marcados en rojo, más abajo.",
        )
    else:
        formulario = PaginaForm(instance=pagina)
        enlaces = EnlaceFormSet(instance=pagina)
    return render(request, "panel/pagina_form.html", {
        "seccion": "paginas",
        "form": formulario,
        "enlaces": enlaces,
        "pagina": pagina,
    })


@GESTION
def pagina_eliminar(request, pk):
    pagina = get_object_or_404(Pagina, pk=pk)
    if request.method != "POST":
        return redirect("panel:pagina_editar", pk=pk)
    titulo = pagina.titulo
    pagina.delete()
    messages.success(request, f"Página «{titulo}» eliminada.")
    return redirect("panel:paginas")


# --- Fechas ----------------------------------------------------------------

@requiere_panel
def fechas_lista(request):
    consulta = Comision.objects.select_related("curso", "curso__categoria")
    cuando = "pasadas" if request.GET.get("cuando") == "pasadas" else "proximas"
    busqueda = request.GET.get("q", "").strip()
    if cuando == "proximas":
        consulta = consulta.filter(fecha_inicio__gte=date.today()).order_by(
            "fecha_inicio", "hora_inicio"
        )
    else:
        consulta = consulta.filter(fecha_inicio__lt=date.today()).order_by("-fecha_inicio")
    if busqueda:
        consulta = consulta.filter(curso__nombre__icontains=busqueda)
    return render(request, "panel/fechas.html", {
        "seccion": "fechas",
        "fechas": consulta,
        "cuando": cuando,
        "q": busqueda,
    })


@GESTION
def fecha_editar(request, pk=None):
    fecha = get_object_or_404(Comision, pk=pk) if pk else None
    if request.method == "POST":
        formulario = FechaForm(request.POST, instance=fecha)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, "Fecha guardada.")
            return redirect("panel:fechas")
        messages.error(request, "Revisá los campos marcados en rojo.")
    else:
        # «+ agregar fecha» desde un curso lo trae ya elegido.
        elegido = request.GET.get("curso", "")
        curso = Curso.objects.filter(pk=elegido).first() if elegido.isdigit() else None
        inicial = {"curso": curso} if curso else {}
        formulario = FechaForm(instance=fecha, initial=inicial)
    return render(request, "panel/fecha_form.html", {
        "seccion": "fechas",
        "form": formulario,
        "comision": fecha,
    })


@GESTION
def fecha_marcar(request, pk):
    """Cambia «visible» o «completa» con un clic, desde el listado o el Tablero."""
    fecha = get_object_or_404(Comision.objects.select_related("curso"), pk=pk)
    campo = request.POST.get("campo")
    if request.method == "POST" and campo in {"visible", "completa"}:
        setattr(fecha, campo, request.POST.get("valor") == "1")
        fecha.save(update_fields=[campo, "actualizado"])
        messages.success(
            request, f"{fecha.curso.nombre}, {fecha.fecha_texto}: {fecha.estado_texto.lower()}."
        )
    return _volver(request, "panel:fechas")


@GESTION
def fecha_eliminar(request, pk):
    fecha = get_object_or_404(Comision.objects.select_related("curso"), pk=pk)
    if request.method != "POST":
        return redirect("panel:fecha_editar", pk=pk)
    descripcion = str(fecha)
    fecha.delete()
    messages.success(request, f"Fecha «{descripcion}» eliminada.")
    return redirect("panel:fechas")


# --- Administración --------------------------------------------------------

def _usuarios_del_panel():
    """Los superusuarios son cuentas técnicas: se administran sólo en /django-admin/."""
    return Usuario.objects.filter(is_superuser=False)


@SOLO_DIRECCION
def usuarios_lista(request):
    usuarios = _usuarios_del_panel().prefetch_related("groups").order_by("first_name", "username")
    por_rol = {rol: [] for rol in JERARQUIA}
    sin_rol = []
    for usuario in usuarios:
        rol = usuario.rol
        (por_rol[rol] if rol else sin_rol).append(usuario)
    return render(request, "panel/usuarios.html", {
        "seccion": "usuarios",
        "grupos": [
            {"rol": rol, "descripcion": DESCRIPCION_ROLES[rol], "usuarios": por_rol[rol]}
            for rol in JERARQUIA
        ],
        "sin_rol": sin_rol,
        "total": usuarios.count(),
    })


@SOLO_DIRECCION
def usuario_editar(request, pk=None):
    usuario = get_object_or_404(_usuarios_del_panel(), pk=pk) if pk else None
    if request.method == "POST":
        formulario = UsuarioForm(request.POST, instance=usuario)
        if formulario.is_valid():
            guardado = formulario.save()
            messages.success(
                request,
                f"Usuario «{guardado.username}» guardado con el rol {guardado.rol_nombre}.",
            )
            return redirect("panel:usuarios")
        messages.error(request, "Revisá los campos marcados en rojo.")
    else:
        formulario = UsuarioForm(instance=usuario)
    return render(request, "panel/usuario_form.html", {
        "seccion": "usuarios",
        "form": formulario,
        "usuario_editado": usuario,
        "puede_eliminar": bool(usuario) and usuario.pk != request.user.pk,
        "descripciones": [(rol.label, DESCRIPCION_ROLES[rol]) for rol in JERARQUIA],
    })


@SOLO_DIRECCION
def usuario_eliminar(request, pk):
    usuario = get_object_or_404(_usuarios_del_panel(), pk=pk)
    if request.method != "POST":
        return redirect("panel:usuario_editar", pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No podés eliminar tu propio usuario.")
        return redirect("panel:usuario_editar", pk=pk)
    nombre = usuario.username
    usuario.delete()
    messages.success(request, f"Usuario «{nombre}» eliminado.")
    return redirect("panel:usuarios")


@SOLO_DIRECCION
def configuracion(request):
    sitio = ConfiguracionSitio.vigente()
    if request.method == "POST":
        formulario = ConfiguracionForm(request.POST, request.FILES, instance=sitio)
        portada = ImagenPortadaFormSet(request.POST, request.FILES, instance=sitio)
        if formulario.is_valid() and portada.is_valid():
            with transaction.atomic():
                formulario.save()
                portada.save()
            messages.success(request, "Configuración del sitio actualizada.")
            return redirect("panel:configuracion")
        messages.error(
            request,
            "Revisá los campos marcados en rojo."
            if not formulario.is_valid()
            else "Revisá las fotos de la portada marcadas en rojo, más abajo.",
        )
    else:
        formulario = ConfiguracionForm(instance=sitio)
        portada = ImagenPortadaFormSet(instance=sitio)
    return render(request, "panel/configuracion.html", {
        "seccion": "configuracion",
        "form": formulario,
        "portada": portada,
    })


@requiere_panel
def ayuda(request):
    """Guía de uso dentro del panel, para no depender de un manual aparte."""
    return render(request, "panel/ayuda.html", {
        "seccion": "ayuda",
        "roles": [(rol.label, DESCRIPCION_ROLES[rol]) for rol in JERARQUIA],
    })
