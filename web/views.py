"""Vistas de la web pública de CETACER."""
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
    """La grilla y sus filtros. Sólo hay filtro para las categorías con cursos.

    Van siempre todas las categorías; la plantilla oculta las que no coinciden
    con el filtro. Uno que no corresponde a ninguna se ignora.
    """
    todas = _catalogo()
    filtro = request.GET.get("categoria", "")
    if not any(b["categoria"].slug == filtro for b in todas):
        filtro = ""
    return {
        "catalogo": todas,
        "filtros": [bloque["categoria"] for bloque in todas],
        "filtro_actual": filtro,
    }


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
