"""Cada curso suma un nombre corto y la web pasa a agruparlos en bloques.

Los cursos de «Renovación» y «Ampliación» se mudan a «Cargas Generales», que
queda con tres botones: Inicial, Renovación y Ampliación. Las categorías se
buscan por identificador y lo que no está se saltea. El nombre corto se pone
sólo cuando no hay duda de qué curso es; si la hay queda vacío, el botón usa
el nombre completo y se corrige desde el panel.
"""
from django.db import migrations, models


def reagrupar(apps, schema_editor):
    Categoria = apps.get_model("cursos", "Categoria")
    Curso = apps.get_model("cursos", "Curso")

    def nombrar(cursos, texto, orden):
        """Sólo si es el único curso del grupo: con dos no se sabe cuál es cuál."""
        if len(cursos) == 1:
            cursos[0].nombre_corto = texto
            cursos[0].orden = orden
            cursos[0].save()

    # Mudar cursos a una categoría oculta los sacaría de la web.
    generales = Categoria.objects.filter(slug="cargas-generales", activa=True).first()
    if generales:
        nombrar(list(Curso.objects.filter(categoria=generales)), "Inicial", 1)
        for slug, texto, orden in (("renovacion", "Renovación", 2), ("ampliacion", "Ampliación", 3)):
            vieja = Categoria.objects.filter(slug=slug).first()
            if not vieja:
                continue
            mudados = list(Curso.objects.filter(categoria=vieja))
            for curso in mudados:
                curso.categoria = generales
                curso.save()
            nombrar(mudados, texto, orden)
            vieja.activa = False
            vieja.save()

    peligrosas = Curso.objects.filter(categoria__slug="mercancias-peligrosas")
    nombrar([c for c in peligrosas if "primera vez" in c.nombre.lower()], "Primera vez", 1)
    nombrar(
        [c for c in peligrosas
         if "renovaci" in c.nombre.lower() or "actualizaci" in c.nombre.lower()],
        "Renovación", 2,
    )


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
