"""Vistas de la web pública de CETACER."""
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from contenido.models import Pagina
from cursos.models import Categoria, ConfiguracionSitio, Curso


def _catalogo():
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
        resultado.append({"categoria": categoria, "cursos": sorted(cursos, key=lambda c: (c.orden, c.nombre))})
    return resultado


def _contexto_catalogo(request):
    """La grilla por bloques. Con `?curso=` se ve sólo ese curso.

    Van siempre todos los cursos; la plantilla oculta los demás. Un curso que
    no existe o no está publicado se ignora y se ven todos.
    """
    bloques = _catalogo()
    elegido = request.GET.get("curso", "")
    publicados = {curso.slug for bloque in bloques for curso in bloque["cursos"]}
    return {"catalogo": bloques, "curso_actual": elegido if elegido in publicados else ""}


def inicio(request):
    return render(request, "web/inicio.html", _contexto_catalogo(request))


def catalogo(request):
    return render(request, "web/catalogo.html", _contexto_catalogo(request))


def pagina(request, slug):
    """Una página de contenido institucional, con sus enlaces agrupados."""
    pagina = get_object_or_404(Pagina.publicadas(), slug=slug)
    return render(request, "web/pagina.html", {
        "pagina": pagina,
        "grupos": pagina.enlaces_agrupados(),
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


def salud(request):
    """Para el monitoreo: 200 si la aplicación llega a la base, 503 si no."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"estado": "error", "base": "error"}, status=503)
    return JsonResponse({"estado": "ok", "base": "ok"})
