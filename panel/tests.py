"""Pruebas del panel: manual de uso y administración de usuarios."""
import re

from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from cuentas.models import JERARQUIA, Rol, Usuario
from cuentas.permisos import sincronizar_grupos

CAPITULOS = [
    "ingresar", "agenda", "cursos", "comisiones", "inscribir", "asistencia",
    "inscripciones", "personas", "paginas", "informes", "administracion", "referencia",
]


class ManualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.usuarios = {}
        for rol in JERARQUIA:
            usuario = Usuario.objects.create_user(
                username=f"prueba_{rol.name.lower()}", password="clave-larga-123"
            )
            usuario.asignar_rol(rol)
            cls.usuarios[rol] = usuario

    def _manual(self, rol):
        self.client.force_login(self.usuarios[rol])
        return self.client.get(reverse("panel:ayuda"))

    def test_todos_los_roles_ven_el_manual_completo(self):
        for rol in JERARQUIA:
            with self.subTest(rol=rol.label):
                respuesta = self._manual(rol)
                self.assertEqual(respuesta.status_code, 200)
                for capitulo in CAPITULOS:
                    self.assertContains(respuesta, f'id="{capitulo}"')

    def test_el_indice_enlaza_a_capitulos_que_existen(self):
        html = self._manual(JERARQUIA[0]).content.decode()
        ids = set(re.findall(r'id="([^"]+)"', html))
        anclas = set(re.findall(r'href="#([^"]+)"', html))
        self.assertTrue(set(CAPITULOS) <= anclas)
        self.assertEqual(anclas - ids, set())

    def test_todas_las_capturas_existen(self):
        html = self._manual(JERARQUIA[0]).content.decode()
        capturas = set(re.findall(r'src="/static/(img/manual/[^"]+)"', html))
        self.assertGreater(len(capturas), 20)
        for ruta in sorted(capturas):
            with self.subTest(captura=ruta):
                self.assertIsNotNone(finders.find(ruta), f"Falta el archivo {ruta}")

    def test_sin_sesion_pide_ingresar(self):
        respuesta = self.client.get(reverse("panel:ayuda"))
        self.assertRedirects(
            respuesta, f"{reverse('panel:login')}?next={reverse('panel:ayuda')}"
        )


class EliminarUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.direccion = cls._crear("marta", Rol.DIRECCION)
        cls.administracion = cls._crear("luis", Rol.ADMINISTRACION)
        cls.recepcion = cls._crear("diego", Rol.RECEPCION)

    @staticmethod
    def _crear(nombre, rol):
        usuario = Usuario.objects.create_user(username=nombre, password="clave-larga-123")
        usuario.asignar_rol(rol)
        return usuario

    def _eliminar(self, quien, a_quien, metodo="post"):
        self.client.force_login(quien)
        return getattr(self.client, metodo)(reverse("panel:usuario_eliminar", args=[a_quien.pk]))

    def _mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def test_direccion_elimina_a_otro_usuario(self):
        respuesta = self._eliminar(self.direccion, self.recepcion)
        self.assertRedirects(respuesta, reverse("panel:usuarios"))
        self.assertFalse(Usuario.objects.filter(pk=self.recepcion.pk).exists())
        self.assertIn("Usuario «diego» eliminado.", self._mensajes(respuesta))

    def test_por_get_no_elimina(self):
        respuesta = self._eliminar(self.direccion, self.recepcion, metodo="get")
        self.assertRedirects(respuesta, reverse("panel:usuario_editar", args=[self.recepcion.pk]))
        self.assertTrue(Usuario.objects.filter(pk=self.recepcion.pk).exists())

    def test_nadie_se_elimina_a_si_mismo(self):
        respuesta = self._eliminar(self.direccion, self.direccion)
        self.assertRedirects(respuesta, reverse("panel:usuario_editar", args=[self.direccion.pk]))
        self.assertTrue(Usuario.objects.filter(pk=self.direccion.pk).exists())

    def test_otros_roles_no_pueden_eliminar(self):
        self._eliminar(self.administracion, self.recepcion)
        self.assertTrue(Usuario.objects.filter(pk=self.recepcion.pk).exists())


    def test_el_boton_aparece_al_editar_a_otro_y_no_a_uno_mismo(self):
        self.client.force_login(self.direccion)
        ajeno = self.client.get(reverse("panel:usuario_editar", args=[self.recepcion.pk]))
        self.assertContains(ajeno, "Eliminar este usuario")
        propio = self.client.get(reverse("panel:usuario_editar", args=[self.direccion.pk]))
        self.assertNotContains(propio, "Eliminar este usuario")
        nuevo = self.client.get(reverse("panel:usuario_nuevo"))
        self.assertNotContains(nuevo, "Eliminar este usuario")


class SuperusuarioOcultoTests(TestCase):
    """El superusuario técnico se administra sólo desde /django-admin/."""

    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.direccion = Usuario.objects.create_user(username="marta", password="clave-larga-123")
        cls.direccion.asignar_rol(Rol.DIRECCION)
        cls.tecnico = Usuario.objects.create_superuser(
            username="tecnico", password="clave-larga-123", email="tecnico@ejemplo.com.ar"
        )
        cls.tecnico.asignar_rol(Rol.DIRECCION)
        cls.sin_rol = Usuario.objects.create_superuser(username="raiz", password="clave-larga-123")

    def test_no_figura_en_el_listado_ni_en_el_total(self):
        self.client.force_login(self.direccion)
        respuesta = self.client.get(reverse("panel:usuarios"))
        self.assertNotContains(respuesta, "tecnico")
        self.assertNotContains(respuesta, "raiz")
        self.assertEqual(respuesta.context["total"], 1)
        self.assertEqual(respuesta.context["sin_rol"], [])

    def test_tampoco_lo_ve_otro_superusuario(self):
        self.client.force_login(self.sin_rol)
        respuesta = self.client.get(reverse("panel:usuarios"))
        self.assertNotContains(respuesta, "tecnico@ejemplo.com.ar")

    def test_no_se_puede_editar_desde_el_panel(self):
        self.client.force_login(self.direccion)
        url = reverse("panel:usuario_editar", args=[self.tecnico.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"username": "otro"}).status_code, 404)
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.username, "tecnico")

    def test_no_se_puede_eliminar_desde_el_panel(self):
        self.client.force_login(self.direccion)
        respuesta = self.client.post(reverse("panel:usuario_eliminar", args=[self.tecnico.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Usuario.objects.filter(pk=self.tecnico.pk).exists())
