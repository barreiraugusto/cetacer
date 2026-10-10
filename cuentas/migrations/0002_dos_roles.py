"""Quedan dos roles. Coordinación pasa a Administración; el resto, sin rol.

Recepción e Instructor existían para inscribir gente y tomar asistencia, que
el panel ya no hace. Sus usuarios no reciben más permisos de los que tenían:
quedan sin rol hasta que Dirección les asigne uno.
"""
from django.db import migrations


def reducir(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Usuario = apps.get_model("cuentas", "Usuario")
    coordinacion = Group.objects.filter(name="Coordinación").first()
    if coordinacion:
        administracion, _ = Group.objects.get_or_create(name="Administración")
        for usuario in Usuario.objects.filter(groups=coordinacion):
            # Quien además tenía Dirección (sólo se arma desde /django-admin/)
            # conserva Dirección: no se lo degrada.
            if not usuario.groups.filter(name="Dirección").exists():
                usuario.groups.add(administracion)
    Group.objects.filter(name__in=["Coordinación", "Recepción", "Instructor"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(reducir, migrations.RunPython.noop)]
