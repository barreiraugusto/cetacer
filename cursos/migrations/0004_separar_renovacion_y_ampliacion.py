from django.db import migrations


def separar(apps, schema_editor):
    """Parte «Renovaciones y ampliaciones» en dos categorías y oculta Pasajeros.

    Los cursos cuyo nombre menciona una ampliación van a «Ampliación»; el resto,
    a «Renovación». La categoría vieja se oculta sólo si queda vacía, para no
    esconder un curso que alguien haya cargado con otro nombre.
    """
    Categoria = apps.get_model("cursos", "Categoria")

    vieja = Categoria.objects.filter(slug="renovaciones-y-ampliaciones").first()
    orden = vieja.orden if vieja else 4
    renovacion, _ = Categoria.objects.get_or_create(
        slug="renovacion",
        defaults={
            "nombre": "Renovación",
            "resumen": "Renovación de la habilitación ya obtenida.",
            "orden": orden,
        },
    )
    ampliacion, _ = Categoria.objects.get_or_create(
        slug="ampliacion",
        defaults={
            "nombre": "Ampliación",
            "resumen": "Ampliación de la habilitación a nuevas categorías.",
            "orden": orden + 1,
        },
    )

    if vieja:
        for curso in vieja.cursos.all():
            curso.categoria = ampliacion if "ampliaci" in curso.nombre.lower() else renovacion
            curso.save(update_fields=["categoria"])
        if not vieja.cursos.exists():
            vieja.activa = False
            vieja.save(update_fields=["activa"])

    Categoria.objects.filter(slug="transporte-de-pasajeros").update(activa=False)


class Migration(migrations.Migration):
    dependencies = [
        ("cursos", "0003_correcciones_web"),
    ]

    operations = [
        migrations.RunPython(separar, migrations.RunPython.noop),
    ]
