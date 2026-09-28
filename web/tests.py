"""Pruebas de la web pública: catálogo, ficha del curso y filtros de plantilla."""
from datetime import date, timedelta
from importlib import import_module

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from contenido.models import EnlacePagina, Pagina
from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso
from web.templatetags.web_extras import texto_curso


class TextoCursoTests(SimpleTestCase):
    def test_las_palabras_en_mayusculas_van_en_negrita(self):
        self.assertEqual(
            texto_curso("- Foto LICENCIA DE CONDUCIR - frente y dorso"),
            "- Foto <strong>LICENCIA DE CONDUCIR</strong> - frente y dorso",
        )

    def test_una_mayuscula_suelta_no_se_resalta(self):
        self.assertEqual(texto_curso("Foto DNI y comprobante"), "Foto <strong>DNI</strong> y comprobante")
        self.assertEqual(texto_curso("A confirmar"), "A confirmar")

    def test_las_direcciones_se_vuelven_enlaces(self):
        html = texto_curso("CERTIFICADO\nhttps://sicapro.com.ar/consultasonline.aspx")
        self.assertEqual(
            html,
            "<strong>CERTIFICADO</strong><br>"
            '<a href="https://sicapro.com.ar/consultasonline.aspx" rel="noopener" '
            'target="_blank">https://sicapro.com.ar/consultasonline.aspx</a>',
        )

    def test_www_sin_esquema_y_punto_final(self):
        html = texto_curso("Turno en www.psicofisicos.com.ar.")
        self.assertIn('href="https://www.psicofisicos.com.ar"', html)
        self.assertTrue(html.endswith("</a>."))

    def test_el_html_se_escapa(self):
        self.assertEqual(texto_curso("<b>hola</b>"), "&lt;b&gt;hola&lt;/b&gt;")


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
        # Todas se dibujan para poder cambiar de filtro sin recargar; las
        # demás van ocultas.
        html = self.client.get("/cursos/?categoria=mercancias-peligrosas").content.decode()
        self.assertRegex(html, r'data-categoria="cargas-generales"\s+hidden')
        self.assertNotRegex(html, r'data-categoria="mercancias-peligrosas"\s+hidden')

    def test_los_filtros_no_vuelven_al_principio_de_la_seccion(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, 'id="filtros"')
        self.assertContains(respuesta, "?categoria=cargas-generales#filtros")
        self.assertContains(respuesta, "js/filtros.js")

    def test_un_filtro_desconocido_muestra_todo(self):
        html = self.client.get("/cursos/?categoria=todas").content.decode()
        self.assertNotRegex(html, r'class="categoria"[^>]*hidden')

    def test_las_categorias_sin_cursos_no_tienen_filtro(self):
        self.assertNotContains(self.client.get("/cursos/"), "?categoria=vacia")

    def test_no_se_ofrece_reservar_lugar(self):
        for url in ("/", "/cursos/", self.curso.get_absolute_url()):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertNotContains(respuesta, "Reservar")
                self.assertNotContains(respuesta, "/inscripcion/")

    def test_las_tarjetas_no_muestran_requisitos_ni_la_volanta(self):
        self.curso.requisitos = "Foto DNI"
        self.curso.save()
        for url in ("/", "/cursos/"):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertNotContains(respuesta, "REQUISITOS")
                self.assertNotContains(respuesta, "AGENDA DE CAPACITACIÓN")
                self.assertContains(respuesta, "Ver requisitos completos")
        self.assertContains(self.client.get(self.curso.get_absolute_url()), "<strong>DNI</strong>")

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

    def test_la_descripcion_tambien_resalta_y_enlaza(self):
        self.curso.descripcion = "CERTIFICADO DE CARGAS\nhttps://sicapro.com.ar/consultasonline.aspx"
        self.curso.save()
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertContains(respuesta, "<strong>CERTIFICADO DE CARGAS</strong>")
        self.assertContains(respuesta, 'href="https://sicapro.com.ar/consultasonline.aspx"')

    def test_la_web_usa_el_logo_sin_la_razon_social(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "logo-cetacer-color-sin-razon")
        self.assertContains(respuesta, "logo-cetacer-blanco-sin-razon")

    def test_la_ficha_no_repite_la_categoria_arriba_del_titulo(self):
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertNotContains(respuesta, 'class="migas"')
        self.assertNotContains(respuesta, "CARGAS GENERALES")
        self.assertContains(respuesta, "caja-fechas")


class EncabezadoYPieTests(TestCase):
    def test_la_portada_no_filtra_comentarios_ni_enlaza_al_calendario(self):
        # Un {# #} de varias líneas Django no lo reconoce y lo imprime como
        # texto: en la portada eso empujaba todo el contenido a la derecha.
        respuesta = self.client.get("/")
        self.assertNotContains(respuesta, "{#")
        self.assertNotContains(respuesta, "Ver calendario de cursos")

    def test_menu_dice_institucional(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, ">Cursos de capacitación</a>")
        self.assertNotContains(respuesta, "Calendario de cursos")
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
