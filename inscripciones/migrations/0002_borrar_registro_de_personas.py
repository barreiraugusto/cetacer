"""CETACER no lleva acá el registro de quienes cursan: se borran las tres tablas.

Va después de cursos.0009, que todavía cuenta inscriptos para saber qué fechas
estaban completas.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inscripciones", "0001_initial"),
        ("cursos", "0009_fechas_visible_y_completa"),
    ]

    # Se borran las tablas enteras, en orden de dependencia. Quitar primero los
    # campos, como propone makemigrations, tropieza con la restricción de
    # unicidad de (comisión, participante).
    operations = [
        migrations.DeleteModel(name="Inscripcion"),
        migrations.DeleteModel(name="Participante"),
        migrations.DeleteModel(name="Empresa"),
    ]
