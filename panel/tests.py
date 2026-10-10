"""Pruebas del manual de uso del panel («Cómo se usa»)."""
import re

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from cuentas.models import JERARQUIA, Usuario
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
