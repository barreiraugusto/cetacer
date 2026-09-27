"""Pruebas de la web pública: catálogo, ficha del curso y filtros de plantilla."""
from datetime import date, timedelta
from importlib import import_module

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from contenido.models import EnlacePagina, Pagina
from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso
from web.templatetags.web_extras import requisitos


class RequisitosTests(SimpleTestCase):
    def test_las_palabras_en_mayusculas_van_en_negrita(self):
        self.assertEqual(
            requisitos("- Foto LICENCIA DE CONDUCIR - frente y dorso"),
            "- Foto <strong>LICENCIA DE CONDUCIR</strong> - frente y dorso",
        )

    def test_una_mayuscula_suelta_no_se_resalta(self):
        self.assertEqual(requisitos("Foto DNI y comprobante"), "Foto <strong>DNI</strong> y comprobante")
        self.assertEqual(requisitos("A confirmar"), "A confirmar")

    def test_las_direcciones_se_vuelven_enlaces(self):
        html = requisitos("CERTIFICADO\nhttps://sicapro.com.ar/consultasonline.aspx")
        self.assertEqual(
            html,
            "<strong>CERTIFICADO</strong><br>"
            '<a href="https://sicapro.com.ar/consultasonline.aspx" rel="noopener" '
            'target="_blank">https://sicapro.com.ar/consultasonline.aspx</a>',
        )

    def test_www_sin_esquema_y_punto_final(self):
        html = requisitos("Turno en www.psicofisicos.com.ar.")
        self.assertIn('href="https://www.psicofisicos.com.ar"', html)
        self.assertTrue(html.endswith("</a>."))

    def test_el_html_se_escapa(self):
        self.assertEqual(requisitos("<b>hola</b>"), "&lt;b&gt;hola&lt;/b&gt;")


class CatalogoTests(TestCase):
    def setUp(self):
        self.cargas = Categoria.objects.create(nombre="Cargas Generales", orden=1)
        self.peligrosas = Categoria.objects.create(nombre="Mercancías Peligrosas", orden=2)
        Categoria.objects.create(nombre="Vacía", orden=3)
        self.curso = Curso.objects.create(
            categoria=self.cargas, nombre="Curso primera vez", precio=1000,
            duracion_horario="3 días",
        )
        Curso.objects.create(categoria=self.peligrosas, nombre="Curso MMPP", precio=1000)
        Comision.objects.create(
            curso=self.curso, fecha_inicio=date.today() + timedelta(days=5),
            estado=Comision.Estado.PUBLICADA,
        )

    def test_sin_filtro_se_ven_todas_las_categorias(self):
        respuesta = self.client.get("/cursos/")
        self.assertContains(respuesta, "Curso primera vez")
        self.assertContains(respuesta, "Curso MMPP")
        self.assertNotContains(respuesta, "Todas las categorías")

    def test_el_filtro_deja_una_sola_categoria(self):
        respuesta = self.client.get("/cursos/?categoria=mercancias-peligrosas")
        self.assertNotContains(respuesta, "Curso primera vez")
        self.assertContains(respuesta, "Curso MMPP")

    def test_un_filtro_desconocido_muestra_todo(self):
        respuesta = self.client.get("/cursos/?categoria=todas")
        self.assertContains(respuesta, "Curso primera vez")
        self.assertContains(respuesta, "Curso MMPP")

    def test_las_categorias_sin_cursos_no_tienen_filtro(self):
        self.assertNotContains(self.client.get("/cursos/"), "?categoria=vacia")

    def test_no_se_ofrece_reservar_lugar(self):
        for url in ("/", "/cursos/", self.curso.get_absolute_url()):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertNotContains(respuesta, "Reservar")
                self.assertNotContains(respuesta, "/inscripcion/")

    def test_la_duracion_ya_no_habla_de_horario(self):
        respuesta = self.client.get("/cursos/")
        self.assertContains(respuesta, "DURACIÓN")
        self.assertNotContains(respuesta, "DURACIÓN Y HORARIO")

    def test_el_pie_de_cursos_remite_a_la_ansv(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "consultaslnc@seguridadvial.gob.ar")
        self.assertNotContains(respuesta, "Boleta de pago para cursos")

    def test_el_video_se_embebe_en_la_seccion_de_cursos(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "Cursos de capacitación")
        self.assertContains(respuesta, "youtube-nocookie.com/embed/0YY-WsyDzD8")

    def test_la_ficha_no_repite_la_categoria_arriba_del_titulo(self):
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertNotContains(respuesta, 'class="migas"')
        self.assertNotContains(respuesta, "CARGAS GENERALES")
        self.assertContains(respuesta, "caja-fechas")


class EncabezadoYPieTests(TestCase):
    def test_menu_dice_institucional(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, ">Institucional</a>")
        self.assertContains(respuesta, "Institucional e información general")
        self.assertNotContains(respuesta, "Categorías C, D y E")

    def test_el_pie_enlaza_instagram(self):
        sitio = ConfiguracionSitio.vigente()
        sitio.instagram = "https://www.instagram.com/cetacer/"
        sitio.save()
        respuesta = self.client.get("/")
        self.assertContains(respuesta, ">Instagram</a>")
        self.assertNotContains(respuesta, "Facebook")

    def test_contacto_muestra_el_whatsapp_de_socios(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "WHATSAPP SOCIOS")
        self.assertContains(respuesta, "https://wa.me/543434503288")


class MigracionesDeDatosTests(TestCase):
    """Las migraciones de datos corren contra la base con sus datos reales."""

    def test_separa_renovacion_y_ampliacion(self):
        vieja = Categoria.objects.create(nombre="Renovaciones y ampliaciones", orden=4)
        pasajeros = Categoria.objects.create(nombre="Transporte de Pasajeros")
        renovacion = Curso.objects.create(categoria=vieja, nombre="Renovación — Cargas")
        ampliacion = Curso.objects.create(categoria=vieja, nombre="Renovación + ampliación — Cargas")

        import_module("cursos.migrations.0004_separar_renovacion_y_ampliacion").separar(apps, None)

        renovacion.refresh_from_db()
        ampliacion.refresh_from_db()
        self.assertEqual(renovacion.categoria.nombre, "Renovación")
        self.assertEqual(ampliacion.categoria.nombre, "Ampliación")
        vieja.refresh_from_db()
        pasajeros.refresh_from_db()
        self.assertFalse(vieja.activa)
        self.assertFalse(pasajeros.activa)

    def test_actualiza_los_enlaces_de_fadeeac_sin_duplicar(self):
        legislacion = Pagina.objects.create(titulo="Legislación")
        fadeeac = EnlacePagina.objects.create(
            pagina=legislacion, titulo="FADEEAC", url="https://www.fadeeac.org.ar/"
        )
        informacion = Pagina.objects.create(titulo="Información útil")
        migracion = import_module("contenido.migrations.0003_enlaces_fadeeac")

        migracion.actualizar(apps, None)
        migracion.actualizar(apps, None)

        fadeeac.refresh_from_db()
        self.assertEqual(fadeeac.url, migracion.FADEEAC_LEGISLACION)
        self.assertEqual(informacion.enlaces.filter(url=migracion.OTRAS_CAMARAS).count(), 1)
