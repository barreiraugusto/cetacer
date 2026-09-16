"""Pruebas de las páginas de contenido institucional."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from contenido.models import EnlacePagina, Pagina


class PaginaTests(TestCase):
    def setUp(self):
        self.pagina = Pagina.objects.create(titulo="Información útil")

    def test_el_slug_se_genera_solo(self):
        self.assertEqual(self.pagina.slug, "informacion-util")

    def test_los_slugs_repetidos_reciben_sufijo(self):
        otra = Pagina.objects.create(titulo="Información útil")
        self.assertEqual(otra.slug, "informacion-util-2")

    def test_publicadas_deja_afuera_las_despublicadas(self):
        Pagina.objects.create(titulo="Borrador", publicada=False)
        self.assertEqual([p.titulo for p in Pagina.publicadas()], ["Información útil"])


class EnlacePaginaTests(TestCase):
    def setUp(self):
        self.pagina = Pagina.objects.create(titulo="Legislación")

    def test_un_enlace_externo_es_valido(self):
        enlace = EnlacePagina(pagina=self.pagina, titulo="IRU", url="https://www.iru.org/")
        enlace.full_clean()

    def test_sin_destino_no_valida(self):
        enlace = EnlacePagina(pagina=self.pagina, titulo="Suelto")
        with self.assertRaises(ValidationError):
            enlace.full_clean()

    def test_con_los_dos_destinos_no_valida(self):
        enlace = EnlacePagina(
            pagina=self.pagina, titulo="Ambos",
            url="https://www.iru.org/", archivo="documentos/guia.pdf",
        )
        with self.assertRaises(ValidationError):
            enlace.full_clean()

    def test_destino_de_un_enlace_externo(self):
        enlace = EnlacePagina.objects.create(
            pagina=self.pagina, titulo="IRU", url="https://www.iru.org/"
        )
        self.assertEqual(enlace.destino, "https://www.iru.org/")
        self.assertFalse(enlace.es_documento)

    def test_destino_de_un_documento(self):
        enlace = EnlacePagina.objects.create(
            pagina=self.pagina, titulo="Guía", archivo="documentos/guia.pdf"
        )
        self.assertEqual(enlace.destino, "/media/documentos/guia.pdf")
        self.assertTrue(enlace.es_documento)

    def test_se_ordenan_por_orden(self):
        EnlacePagina.objects.create(pagina=self.pagina, titulo="B", url="https://b.test/", orden=2)
        EnlacePagina.objects.create(pagina=self.pagina, titulo="A", url="https://a.test/", orden=1)
        self.assertEqual([e.titulo for e in self.pagina.enlaces.all()], ["A", "B"])


class EnlacesAgrupadosTests(TestCase):
    def setUp(self):
        self.pagina = Pagina.objects.create(titulo="Información útil")

    def _enlace(self, titulo, grupo="", orden=0, activo=True):
        return EnlacePagina.objects.create(
            pagina=self.pagina, titulo=titulo, grupo=grupo,
            url=f"https://{titulo.lower()}.test/", orden=orden, activo=activo,
        )

    def test_los_sueltos_van_primero(self):
        self._enlace("Agrupado", grupo="Organismos", orden=1)
        self._enlace("Suelto", orden=2)
        grupos = self.pagina.enlaces_agrupados()
        self.assertEqual(grupos[0][0], "")
        self.assertEqual([e.titulo for e in grupos[0][1]], ["Suelto"])

    def test_respeta_el_orden_de_aparicion_de_los_grupos(self):
        self._enlace("Uno", grupo="Segundo", orden=1)
        self._enlace("Dos", grupo="Primero", orden=2)
        self.assertEqual(
            [nombre for nombre, _ in self.pagina.enlaces_agrupados()],
            ["Segundo", "Primero"],
        )

    def test_agrupa_los_que_comparten_grupo(self):
        self._enlace("Uno", grupo="Organismos", orden=1)
        self._enlace("Dos", grupo="Organismos", orden=2)
        grupos = self.pagina.enlaces_agrupados()
        self.assertEqual(len(grupos), 1)
        self.assertEqual([e.titulo for e in grupos[0][1]], ["Uno", "Dos"])

    def test_los_inactivos_no_aparecen(self):
        self._enlace("Visible", orden=1)
        self._enlace("Oculto", orden=2, activo=False)
        grupos = self.pagina.enlaces_agrupados()
        self.assertEqual([e.titulo for e in grupos[0][1]], ["Visible"])

    def test_pagina_sin_enlaces_devuelve_lista_vacia(self):
        self.assertEqual(self.pagina.enlaces_agrupados(), [])
