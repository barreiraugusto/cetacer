from django.core.management.base import BaseCommand

from cuentas.permisos import sincronizar_grupos


class Command(BaseCommand):
    help = "Crea los grupos de la jerarquía del panel y les asigna sus permisos."

    def handle(self, *args, **opciones):
        self.stdout.write("Sincronizando grupos y permisos...")
        resultado = sincronizar_grupos(verbose=True)
        self.stdout.write(
            self.style.SUCCESS(f"Listo: {len(resultado)} grupos sincronizados.")
        )
