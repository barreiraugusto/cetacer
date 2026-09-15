from cursos.models import ConfiguracionSitio


def configuracion_sitio(request):
    """La configuración institucional está disponible en todas las plantillas."""
    try:
        return {"sitio": ConfiguracionSitio.vigente()}
    except Exception:
        # Durante las migraciones iniciales la tabla todavía no existe.
        return {"sitio": None}
