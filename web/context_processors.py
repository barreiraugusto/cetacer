from cursos.models import ConfiguracionSitio


def configuracion_sitio(request):
    """La configuración institucional está disponible en todas las plantillas."""
    try:
        return {"sitio": ConfiguracionSitio.vigente()}
    except Exception:
        # Durante las migraciones iniciales la tabla todavía no existe.
        return {"sitio": None}


def paginas_de_contenido(request):
    """Las páginas publicadas, para que cualquier plantilla pueda enlazarlas.

    Va aparte de `configuracion_sitio` para que un error en una no deje sin
    contexto a la otra.
    """
    from contenido.models import Pagina

    try:
        return {"paginas": {p.slug: p for p in Pagina.publicadas()}}
    except Exception:
        # Durante las migraciones iniciales la tabla todavía no existe.
        return {"paginas": {}}
