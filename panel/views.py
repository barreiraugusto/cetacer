"""Vistas del panel de administración de CETACER."""
from datetime import date, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from contenido.models import Pagina
from cuentas.models import DESCRIPCION_ROLES, JERARQUIA, Rol, Usuario
from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso

from .accesos import (
    GESTION_CATALOGO,
    GESTION_COMISIONES,
    LECTURA_INSTITUCIONAL,
    SOLO_DIRECCION,
    comisiones_visibles,
    requiere_panel,
)
from .forms import (
    CategoriaForm,
    ComisionForm,
    ConfiguracionForm,
    CursoForm,
    EnlaceFormSet,
    ImagenPortadaFormSet,
    PaginaForm,
    UsuarioForm,
)


# --- Tablero ---------------------------------------------------------------

@requiere_panel
def inicio(request):
    """Tablero de entrada: las próximas fechas, en un vistazo."""
    hoy = date.today()
    comisiones = comisiones_visibles(
        request.user, Comision.objects.select_related("curso", "curso__categoria")
    )
    return render(request, "panel/inicio.html", {
        "seccion": "inicio",
        "indicadores": {
            "comisiones_abiertas": comisiones.filter(
                fecha_inicio__gte=hoy, estado=Comision.Estado.PUBLICADA
            ).count(),
        },
        "proximas": comisiones.filter(fecha_inicio__gte=hoy).order_by("fecha_inicio")[:6],
    })


@requiere_panel
def agenda(request):
    """Calendario mensual de comisiones."""
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

    comisiones = comisiones_visibles(
        request.user, Comision.objects.select_related("curso", "curso__categoria")
    ).filter(fecha_inicio__gte=primero, fecha_inicio__lt=siguiente).order_by("fecha_inicio")

    por_dia = {}
    for comision in comisiones:
        por_dia.setdefault(comision.fecha_inicio.day, []).append(comision)

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
        "total": comisiones.count(),
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


@GESTION_CATALOGO
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


@GESTION_CATALOGO
def curso_eliminar(request, pk):
    curso = get_object_or_404(Curso, pk=pk)
    if request.method != "POST":
        return redirect("panel:curso_editar", pk=pk)
    if curso.comisiones.exists():
        messages.error(
            request,
            "Ese curso tiene comisiones cargadas. Desactivalo en lugar de borrarlo "
            "para no perder el historial de participantes.",
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


@GESTION_CATALOGO
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


@LECTURA_INSTITUCIONAL
def paginas_lista(request):
    return render(request, "panel/paginas.html", {
        "seccion": "paginas",
        "paginas_cargadas": Pagina.objects.prefetch_related("enlaces"),
    })


@GESTION_CATALOGO
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


@GESTION_CATALOGO
def pagina_eliminar(request, pk):
    pagina = get_object_or_404(Pagina, pk=pk)
    if request.method != "POST":
        return redirect("panel:pagina_editar", pk=pk)
    titulo = pagina.titulo
    pagina.delete()
    messages.success(request, f"Página «{titulo}» eliminada.")
    return redirect("panel:paginas")


# --- Comisiones ------------------------------------------------------------

def _puede_gestionar_comisiones(usuario):
    """Lo mismo que exige GESTION_COMISIONES, para decidir qué botones mostrar."""
    return usuario.is_superuser or usuario.alcanza(Rol.COORDINACION)


@requiere_panel
def comisiones_lista(request):
    consulta = comisiones_visibles(
        request.user,
        Comision.objects.select_related("curso", "curso__categoria", "instructor"),
    )
    estado = request.GET.get("estado", "")
    cuando = request.GET.get("cuando", "proximas")
    busqueda = request.GET.get("q", "").strip()
    if estado:
        consulta = consulta.filter(estado=estado)
    if cuando == "proximas":
        consulta = consulta.filter(fecha_inicio__gte=date.today())
    elif cuando == "pasadas":
        consulta = consulta.filter(fecha_inicio__lt=date.today()).order_by("-fecha_inicio")
    if busqueda:
        consulta = consulta.filter(curso__nombre__icontains=busqueda)
    return render(request, "panel/comisiones.html", {
        "seccion": "comisiones",
        "comisiones": consulta,
        "estados": Comision.Estado.choices,
        "estado_sel": estado,
        "cuando": cuando,
        "q": busqueda,
        "puede_gestionar": _puede_gestionar_comisiones(request.user),
    })


@GESTION_COMISIONES
def comision_editar(request, pk=None):
    comision = get_object_or_404(Comision, pk=pk) if pk else None
    if request.method == "POST":
        formulario = ComisionForm(request.POST, instance=comision)
        if formulario.is_valid():
            guardada = formulario.save()
            messages.success(request, "Comisión guardada.")
            return redirect("panel:comisiones")
        messages.error(request, "Revisá los campos marcados en rojo.")
    else:
        inicial = {}
        curso_id = request.GET.get("curso")
        if curso_id:
            curso = Curso.objects.filter(pk=curso_id).first()
            if curso:
                inicial = {"curso": curso, "cupo": curso.cupo_sugerido}
        formulario = ComisionForm(instance=comision, initial=inicial)
    return render(request, "panel/comision_form.html", {
        "seccion": "comisiones",
        "form": formulario,
        "comision": comision,
    })


@GESTION_COMISIONES
def comision_eliminar(request, pk):
    comision = get_object_or_404(Comision, pk=pk)
    if request.method != "POST":
        return redirect("panel:comision_editar", pk=pk)
    descripcion = str(comision)
    comision.delete()
    messages.success(request, f"Comisión «{descripcion}» eliminada.")
    return redirect("panel:comisiones")


@GESTION_COMISIONES
def comision_cambiar_estado(request, pk):
    comision = get_object_or_404(Comision, pk=pk)
    if request.method != "POST":
        return redirect("panel:comisiones")
    nuevo = request.POST.get("estado")
    validos = {valor for valor, _ in Comision.Estado.choices}
    if nuevo not in validos:
        messages.error(request, "Ese estado no existe.")
    else:
        comision.estado = nuevo
        comision.save(update_fields=["estado", "actualizado"])
        messages.success(request, f"La comisión pasó a «{comision.get_estado_display()}».")
    return redirect("panel:comisiones")


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
