from django.db import migrations, models


class Migration(migrations.Migration):
    """Correcciones de la web de septiembre de 2026.

    El campo de Facebook ya guardaba el enlace de Instagram, así que se renombra
    en lugar de borrarse: el dato cargado se conserva.
    """

    dependencies = [
        ("cursos", "0002_remove_curso_link_externo_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="configuracionsitio",
            old_name="facebook",
            new_name="instagram",
        ),
        migrations.AlterField(
            model_name="configuracionsitio",
            name="instagram",
            field=models.URLField(blank=True, verbose_name="Instagram"),
        ),
        migrations.AddField(
            model_name="configuracionsitio",
            name="video_cursos",
            field=models.URLField(
                blank=True,
                default="https://www.youtube.com/watch?v=0YY-WsyDzD8",
                help_text="Enlace de YouTube. Si se deja vacío, la sección va sin video.",
                verbose_name="video de la sección de cursos",
            ),
        ),
        migrations.AddField(
            model_name="configuracionsitio",
            name="whatsapp_socios",
            field=models.CharField(
                blank=True,
                default="(0343) 4503288",
                help_text="Con la característica. Ej: (0343) 4503288",
                max_length=40,
                verbose_name="WhatsApp de socios",
            ),
        ),
        migrations.AlterField(
            model_name="configuracionsitio",
            name="descripcion_larga",
            field=models.CharField(
                blank=True,
                default="CÁMARA EMPRESARIA DEL TRANSPORTE AUTOMOTOR DE CARGAS DE ENTRE RÍOS",
                help_text="Se muestra en la pantalla de ingreso del panel.",
                max_length=200,
                verbose_name="razón social",
            ),
        ),
    ]
