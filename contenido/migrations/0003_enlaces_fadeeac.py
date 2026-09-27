from django.db import migrations

FADEEAC_RAIZ = ("https://www.fadeeac.org.ar/", "https://www.fadeeac.org.ar")
FADEEAC_LEGISLACION = "https://www.fadeeac.org.ar/departamento-legislacion-legales-y-seguros/"
OTRAS_CAMARAS = "https://www.fadeeac.org.ar/entidades-asociadas/"


def actualizar(apps, schema_editor):
    """Apunta FADEEAC de Legislación a su departamento y suma «Otras cámaras».

    Sólo toca lo que sigue como se sembró: si alguien ya cambió el enlace o
    cargó las cámaras a mano desde el panel, no se pisa ni se duplica.
    """
    Pagina = apps.get_model("contenido", "Pagina")
    EnlacePagina = apps.get_model("contenido", "EnlacePagina")

    EnlacePagina.objects.filter(
        pagina__slug="legislacion", url__in=FADEEAC_RAIZ
    ).update(url=FADEEAC_LEGISLACION)

    informacion = Pagina.objects.filter(slug="informacion-util").first()
    if informacion and not informacion.enlaces.filter(url=OTRAS_CAMARAS).exists():
        ultimo = informacion.enlaces.order_by("-orden").first()
        EnlacePagina.objects.create(
            pagina=informacion,
            titulo="Otras cámaras",
            descripcion="Entidades asociadas a FADEEAC en todo el país.",
            grupo="FADEEAC",
            url=OTRAS_CAMARAS,
            orden=(ultimo.orden + 1) if ultimo else 1,
            activo=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("contenido", "0002_alter_enlacepagina_archivo"),
    ]

    operations = [
        migrations.RunPython(actualizar, migrations.RunPython.noop),
    ]
