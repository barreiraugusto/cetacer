"""Cada fecha pasa a tener sólo dos datos de estado: visible y completa.

Se calcula acá, mientras todavía existen el estado viejo, el cupo y las
inscripciones; las migraciones siguientes borran las tres cosas.
"""
from django.db import migrations, models
from django.db.models import Count, F, Q


def pasar_estado(apps, schema_editor):
    Comision = apps.get_model("cursos", "Comision")
    publicadas = ["publicada", "en_curso"]
    Comision.objects.filter(estado__in=publicadas).update(visible=True)
    Comision.objects.exclude(estado__in=publicadas).update(visible=False)
    # Igual que la regla vieja (inscriptos >= cupo), cupo en cero incluido: la
    # migración no cambia lo que la web le muestra hoy al público.
    llenas = (
        Comision.objects.annotate(
            ocupados=Count("inscripciones", filter=~Q(inscripciones__estado="cancelada"))
        )
        .filter(ocupados__gte=F("cupo"))
        .values_list("pk", flat=True)
    )
    Comision.objects.filter(pk__in=list(llenas)).update(completa=True)


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0008_comision_marcar_completa"),
        ("inscripciones", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="comision",
            name="visible",
            field=models.BooleanField(
                default=True,
                help_text="Destildala para guardar la fecha sin publicarla.",
                verbose_name="visible en la web",
            ),
        ),
        migrations.RenameField(model_name="comision", old_name="cerrada", new_name="completa"),
        migrations.AlterField(
            model_name="comision",
            name="completa",
            field=models.BooleanField(
                default=False,
                help_text="La web muestra la fecha como «Completo» en lugar de «Disponible».",
                verbose_name="completo",
            ),
        ),
        migrations.RunPython(pasar_estado, migrations.RunPython.noop),
    ]
