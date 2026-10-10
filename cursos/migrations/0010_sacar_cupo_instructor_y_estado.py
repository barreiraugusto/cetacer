"""Una fecha ya no lleva cupo, instructor, estado ni observaciones."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0009_fechas_visible_y_completa"),
        ("inscripciones", "0002_borrar_registro_de_personas"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="comision",
            options={
                "ordering": ["fecha_inicio", "hora_inicio"],
                "verbose_name": "fecha",
                "verbose_name_plural": "fechas",
            },
        ),
        migrations.RemoveIndex(
            model_name="comision",
            name="cursos_comi_fecha_i_7b8102_idx",
        ),
        migrations.RemoveField(
            model_name="comision",
            name="cupo",
        ),
        migrations.RemoveField(
            model_name="comision",
            name="estado",
        ),
        migrations.RemoveField(
            model_name="comision",
            name="instructor",
        ),
        migrations.RemoveField(
            model_name="comision",
            name="observaciones",
        ),
        migrations.RemoveField(
            model_name="curso",
            name="cupo_sugerido",
        ),
        migrations.RemoveField(
            model_name="curso",
            name="cupo_texto",
        ),
        migrations.AddIndex(
            model_name="comision",
            index=models.Index(
                fields=["fecha_inicio", "visible"],
                name="cursos_comi_fecha_i_1fcd69_idx",
            ),
        ),
    ]
