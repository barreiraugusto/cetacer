"""Cada curso suma un nombre corto y la web pasa a agruparlos en bloques.

Los cursos de «Renovación» y «Ampliación» se mudan a «Cargas Generales», que
queda con tres botones: Inicial, Renovación y Ampliación. Las categorías y
cursos se buscan por identificador; lo que no está, se saltea.
"""
from django.db import migrations, models


def reagrupar(apps, schema_editor):
    Categoria = apps.get_model("cursos", "Categoria")
    Curso = apps.get_model("cursos", "Curso")

    def nombrar(curso, texto, orden=None):
        # Un nombre corto ya cargado a mano no se pisa.
        if not curso.nombre_corto:
            curso.nombre_corto = texto
        if orden is not None:
            curso.orden = orden
        curso.save()

    generales = Categoria.objects.filter(slug="cargas-generales").first()
    if generales:
        for curso in Curso.objects.filter(categoria=generales):
            nombrar(curso, "Inicial", 1)
        for slug, texto, orden in (("renovacion", "Renovación", 2), ("ampliacion", "Ampliación", 3)):
            vieja = Categoria.objects.filter(slug=slug).first()
            if not vieja:
                continue
            for curso in Curso.objects.filter(categoria=vieja):
                curso.categoria = generales
                nombrar(curso, texto, orden)
            vieja.activa = False
            vieja.save()

    for curso in Curso.objects.filter(categoria__slug="mercancias-peligrosas"):
        primera = "primera vez" in curso.nombre.lower()
        nombrar(curso, "Primera vez" if primera else "Renovación")


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0010_sacar_cupo_instructor_y_estado"),
    ]

    operations = [
        migrations.AddField(
            model_name="curso",
            name="nombre_corto",
            field=models.CharField(
                blank=True,
                help_text="Texto del botón del curso en la web. Ej: Inicial, Renovación.",
                max_length=40,
                verbose_name="nombre corto",
            ),
        ),
        migrations.RunPython(reagrupar, migrations.RunPython.noop),
    ]
