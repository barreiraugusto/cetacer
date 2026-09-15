"""Pruebas de la jerarquía de roles."""
from django.contrib.auth.models import Group
from django.test import TestCase

from cuentas.models import Rol, Usuario
from cuentas.permisos import sincronizar_grupos


class JerarquiaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()

    def _usuario(self, nombre, rol=None):
        usuario = Usuario.objects.create_user(username=nombre, password="clave-larga-123")
        if rol:
            usuario.asignar_rol(rol)
        return usuario

    def test_sincronizar_grupos_crea_los_cinco_roles(self):
        self.assertEqual(Group.objects.filter(name__in=[r.value for r in Rol]).count(), 5)

    def test_sincronizar_grupos_es_idempotente(self):
        antes = Group.objects.get(name=Rol.RECEPCION.value).permissions.count()
        sincronizar_grupos()
        despues = Group.objects.get(name=Rol.RECEPCION.value).permissions.count()
        self.assertEqual(antes, despues)

    def test_rol_devuelve_el_grupo_asignado(self):
        usuario = self._usuario("silvia", Rol.COORDINACION)
        self.assertEqual(usuario.rol, Rol.COORDINACION)
        self.assertEqual(usuario.rol_nombre, "Coordinación")

    def test_usuario_sin_grupo_no_tiene_rol(self):
        self.assertIsNone(self._usuario("nadie").rol)

    def test_superusuario_siempre_es_direccion(self):
        admin = Usuario.objects.create_superuser(username="root", password="clave-larga-123")
        self.assertEqual(admin.rol, Rol.DIRECCION)

    def test_alcanza_respeta_el_orden_de_la_jerarquia(self):
        direccion = self._usuario("marta", Rol.DIRECCION)
        recepcion = self._usuario("diego", Rol.RECEPCION)
        # Dirección alcanza todos los niveles de abajo.
        self.assertTrue(direccion.alcanza(Rol.RECEPCION))
        self.assertTrue(direccion.alcanza(Rol.DIRECCION))
        # Recepción no alcanza los de arriba.
        self.assertFalse(recepcion.alcanza(Rol.COORDINACION))
        self.assertTrue(recepcion.alcanza(Rol.RECEPCION))

    def test_asignar_rol_reemplaza_el_anterior(self):
        usuario = self._usuario("cambia", Rol.RECEPCION)
        usuario.asignar_rol(Rol.ADMINISTRACION)
        self.assertEqual(usuario.groups.count(), 1)
        self.assertEqual(usuario.rol, Rol.ADMINISTRACION)

    def test_iniciales_y_nombre_completo(self):
        usuario = self._usuario("ana")
        usuario.first_name, usuario.last_name = "Ana", "Pérez"
        self.assertEqual(usuario.nombre_completo, "Ana Pérez")
        self.assertEqual(usuario.iniciales, "AP")


class FiltroPluralTests(TestCase):
    """El plural en español no siempre se arma agregando letras al final."""

    def test_singular(self):
        from panel.templatetags.formato import plural

        self.assertEqual(plural(1, "comisión"), "comisión")

    def test_palabras_con_tilde_pierden_el_acento(self):
        from panel.templatetags.formato import plural

        self.assertEqual(plural(3, "comisión"), "comisiones")
        self.assertEqual(plural(0, "inscripción"), "inscripciones")

    def test_plural_regular(self):
        from panel.templatetags.formato import plural

        self.assertEqual(plural(2, "curso"), "cursos")
        self.assertEqual(plural(2, "mes"), "meses")
