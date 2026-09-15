"""Vistas de la web pública de CETACER."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from cursos.models import Categoria, ConfiguracionSitio, Curso
from inscripciones.models import Empresa, Inscripcion, Participante
from panel.forms import PreinscripcionForm


def _catalogo(filtro=None):
    """Categorías activas con sus cursos publicados, listo para la grilla."""
    categorias = (
        Categoria.objects.filter(activa=True)
        .prefetch_related("cursos__comisiones")
        .distinct()
    )
    resultado = []
    for categoria in categorias:
        cursos = [c for c in categoria.cursos.all() if c.activo]
        if not cursos:
            continue
        if filtro and filtro != "todas" and categoria.slug != filtro:
            continue
        resultado.append({"categoria": categoria, "cursos": sorted(cursos, key=lambda c: (c.orden, c.nombre))})
    return resultado


def inicio(request):
    filtro = request.GET.get("categoria", "todas")
    return render(request, "web/inicio.html", {
        "catalogo": _catalogo(filtro),
        "filtros": Categoria.objects.filter(activa=True),
        "filtro_actual": filtro,
    })


def catalogo(request):
    filtro = request.GET.get("categoria", "todas")
    return render(request, "web/catalogo.html", {
        "catalogo": _catalogo(filtro),
        "filtros": Categoria.objects.filter(activa=True),
        "filtro_actual": filtro,
    })


def curso_detalle(request, slug):
    curso = get_object_or_404(
        Curso.objects.select_related("categoria"), slug=slug, activo=True
    )
    sitio = ConfiguracionSitio.vigente()
    return render(request, "web/curso.html", {
        "curso": curso,
        "comisiones": curso.comisiones_publicadas(),
        "whatsapp_curso": sitio.enlace_whatsapp(
            f"Hola, quisiera pedir turno para: {curso.nombre}"
        ),
        "relacionados": Curso.objects.filter(
            categoria=curso.categoria, activo=True
        ).exclude(pk=curso.pk)[:3],
    })


def preinscripcion(request, slug):
    """Solicitud de turno desde la web. Entra al panel como «preinscripta»."""
    curso = get_object_or_404(Curso, slug=slug, activo=True)
    sitio = ConfiguracionSitio.vigente()

    if not sitio.inscripcion_online:
        return redirect("web:curso", slug=slug)

    if not curso.tiene_fechas:
        messages.info(
            request,
            "Este curso todavía no tiene fechas publicadas. Escribinos por WhatsApp y te avisamos.",
        )
        return redirect("web:curso", slug=slug)

    if request.method == "POST":
        formulario = PreinscripcionForm(curso, request.POST)
        if formulario.is_valid():
            datos = formulario.cleaned_data
            with transaction.atomic():
                empresa = None
                if datos["empresa"]:
                    empresa, _ = Empresa.objects.get_or_create(
                        razon_social=datos["empresa"].strip()
                    )
                participante, creado = Participante.objects.get_or_create(
                    dni=datos["dni"],
                    defaults={
                        "apellido": datos["apellido"],
                        "nombre": datos["nombre"],
                        "telefono": datos["telefono"],
                        "email": datos["email"],
                        "localidad": datos["localidad"],
                        "empresa": empresa,
                    },
                )
                if not creado:
                    participante.telefono = datos["telefono"] or participante.telefono
                    participante.email = datos["email"] or participante.email
                    participante.localidad = datos["localidad"] or participante.localidad
                    if empresa and not participante.empresa:
                        participante.empresa = empresa
                    participante.save()

                Inscripcion.objects.get_or_create(
                    comision=datos["comision"],
                    participante=participante,
                    defaults={
                        "estado": Inscripcion.Estado.PREINSCRIPTO,
                        "origen": "web",
                    },
                )
            request.session["preinscripcion"] = {
                "curso": curso.nombre,
                "fecha": datos["comision"].fecha_texto,
                "nombre": participante.nombre,
            }
            return redirect("web:preinscripcion_ok")
    else:
        formulario = PreinscripcionForm(curso)

    return render(request, "web/preinscripcion.html", {
        "curso": curso,
        "form": formulario,
    })


def preinscripcion_ok(request):
    datos = request.session.pop("preinscripcion", None)
    if not datos:
        return redirect("web:inicio")
    return render(request, "web/preinscripcion_ok.html", {"datos": datos})
