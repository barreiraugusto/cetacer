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
