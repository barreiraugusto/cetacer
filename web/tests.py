"""Pruebas de la web pública: catálogo, ficha del curso y filtros de plantilla."""
import re
from datetime import date, timedelta
from importlib import import_module
from unittest import mock

from django.apps import apps
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

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
        )

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


class SaludTests(TestCase):
    def test_ok_con_la_base_disponible(self):
        respuesta = self.client.get("/salud/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "ok", "base": "ok"})

    def test_503_si_la_base_no_responde(self):
        # Sin tocar la base, /salud/ daría 200 con PostgreSQL caído y ni el
        # monitor del servidor ni uno externo tendrían cómo enterarse.
        with mock.patch(
            "web.views.connection.cursor",
            side_effect=OperationalError("connection refused"),
        ):
            respuesta = self.client.get("/salud/")
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {"estado": "error", "base": "error"})


class WebPublicaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre="Cargas Generales")
        cls.curso = Curso.objects.create(
            categoria=categoria, nombre="Curso primera vez", precio=405000,
            requisitos="Psicofísico vigente.",
        )
        cls.comision = Comision.objects.create(
            curso=cls.curso, fecha_inicio=date.today() + timedelta(days=15),
        )

    def test_el_inicio_muestra_los_cursos_activos(self):
        respuesta = self.client.get(reverse("web:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Curso primera vez")
        self.assertContains(respuesta, "$405.000")

    def test_un_curso_desactivado_no_aparece(self):
        self.curso.activo = False
        self.curso.save()
        respuesta = self.client.get(reverse("web:inicio"))
        self.assertNotContains(respuesta, "Curso primera vez")

    def test_la_ficha_del_curso_lista_las_fechas_publicadas(self):
        respuesta = self.client.get(reverse("web:curso", kwargs={"slug": self.curso.slug}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.comision.fecha_texto)

    def test_la_web_no_ofrece_reservar_lugar(self):
        """CETACER pidió sacar la reserva online: los turnos van por WhatsApp."""
        for url in (
            reverse("web:inicio"),
            reverse("web:catalogo"),
            reverse("web:curso", kwargs={"slug": self.curso.slug}),
        ):
            html = self.client.get(url).content.decode()
            self.assertNotIn("Reservar", html, f"quedó un botón de reserva en {url}")
            self.assertNotIn("/inscripcion/", html, f"quedó un enlace de reserva en {url}")

    def test_no_queda_ninguna_ruta_publica_de_reserva(self):
        """Sacar el botón no alcanza: la dirección tampoco tiene que existir."""
        from django.urls import NoReverseMatch

        for nombre in ("web:preinscripcion", "web:preinscripcion_ok"):
            with self.assertRaises(NoReverseMatch):
                reverse(nombre, kwargs={"slug": self.curso.slug})

        self.assertEqual(
            self.client.get(f"/cursos/{self.curso.slug}/inscripcion/").status_code, 404
        )
        self.assertEqual(self.client.post(f"/cursos/{self.curso.slug}/inscripcion/").status_code, 404)

    def test_la_ficha_no_enlaza_la_boleta_de_pago(self):
        """La boleta se reemplazó por el texto de ANSV al pie de los cursos."""
        html = self.client.get(
            reverse("web:curso", kwargs={"slug": self.curso.slug})
        ).content.decode()
        self.assertNotIn("sicapro", html.lower())
        self.assertNotIn("Boleta de pago", html)


class EstadoDeFechaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre="Cargas Generales")
        cls.curso = Curso.objects.create(categoria=categoria, nombre="Inicial", precio=1)
        manana = date.today() + timedelta(days=1)
        Comision.objects.create(curso=cls.curso, fecha_inicio=manana)
        Comision.objects.create(curso=cls.curso, fecha_inicio=manana + timedelta(days=7), completa=True)
        Comision.objects.create(curso=cls.curso, fecha_inicio=manana + timedelta(days=14), visible=False)

    def _paginas(self):
        return [self.client.get("/"), self.client.get("/cursos/"),
                self.client.get(self.curso.get_absolute_url())]

    def test_cada_fecha_lleva_su_estado(self):
        for respuesta in self._paginas():
            with self.subTest(pagina=respuesta.request["PATH_INFO"]):
                self.assertContains(respuesta, 'class="estado-fecha estado-fecha--disponible">Disponible<', count=1)
                self.assertContains(respuesta, 'class="estado-fecha estado-fecha--completa">Completo<', count=1)

    def test_la_fecha_oculta_no_aparece(self):
        for respuesta in self._paginas():
            with self.subTest(pagina=respuesta.request["PATH_INFO"]):
                self.assertNotContains(respuesta, "Oculta")
                self.assertNotContains(respuesta, "estado-fecha--oculta")

    def test_ya_no_se_habla_de_lugares_ni_de_cupo(self):
        for respuesta in self._paginas():
            with self.subTest(pagina=respuesta.request["PATH_INFO"]):
                html = respuesta.content.decode()
                self.assertNotRegex(html, r"\d+ lugar")
                self.assertNotIn("CUPO", html)
                self.assertNotIn("Cupo", html)
                self.assertNotIn("cupo-barra", html)


class BloquesTests(TestCase):
    """Cada categoría es un bloque y cada curso, un botón que lo deja solo a la vista."""

    @classmethod
    def setUpTestData(cls):
        generales = Categoria.objects.create(nombre="Cargas Generales", orden=1)
        peligrosas = Categoria.objects.create(nombre="Mercancías Peligrosas", orden=2)
        Categoria.objects.create(nombre="Transporte de Pasajeros", orden=3)
        cls.inicial = Curso.objects.create(
            categoria=generales, nombre="Curso primera vez — Cargas Generales",
            nombre_corto="Inicial", precio=1, orden=1,
        )
        cls.renovacion = Curso.objects.create(
            categoria=generales, nombre="Renovación — Cargas Generales",
            nombre_corto="Renovación", precio=1, orden=2,
        )
        cls.peligrosas = Curso.objects.create(
            categoria=peligrosas, nombre="Curso primera vez — Mercancías Peligrosas", precio=1,
        )
        cls.oculto = Curso.objects.create(
            categoria=generales, nombre="Viejo", nombre_corto="Viejo", precio=1, activo=False,
        )

    def _tarjetas_visibles(self, respuesta):
        html = respuesta.content.decode()
        return re.findall(r'<article class="tarjeta-curso" data-curso="([^"]+)">', html)

    def _botones(self, respuesta):
        html = respuesta.content.decode()
        return re.findall(r'<a class="boton-curso[^>]*data-curso="([^"]+)"[^>]*>([^<]+)</a>', html)

    def test_sin_elegir_se_ven_todos_los_cursos(self):
        respuesta = self.client.get("/")
        self.assertEqual(
            self._tarjetas_visibles(respuesta),
            [self.inicial.slug, self.renovacion.slug, self.peligrosas.slug],
        )
        self.assertNotContains(respuesta, "boton-curso--activo")

    def test_cada_curso_tiene_su_boton_con_el_nombre_corto(self):
        self.assertEqual(self._botones(self.client.get("/")), [
            (self.inicial.slug, "Inicial"),
            (self.renovacion.slug, "Renovación"),
            (self.peligrosas.slug, "Curso primera vez — Mercancías Peligrosas"),
        ])

    def test_elegir_un_curso_muestra_solo_ese(self):
        respuesta = self.client.get("/?curso=" + self.renovacion.slug)
        self.assertEqual(self._tarjetas_visibles(respuesta), [self.renovacion.slug])
        self.assertContains(respuesta, "boton-curso--activo", count=1)

    def test_los_bloques_y_sus_botones_siguen_a_la_vista(self):
        respuesta = self.client.get("/?curso=" + self.renovacion.slug)
        self.assertContains(respuesta, "Mercancías Peligrosas")
        self.assertEqual(len(self._botones(respuesta)), 3)

    def test_un_curso_desconocido_o_inactivo_muestra_todo(self):
        for slug in ("no-existe", self.oculto.slug, ""):
            with self.subTest(slug=slug):
                respuesta = self.client.get("/?curso=" + slug)
                self.assertEqual(len(self._tarjetas_visibles(respuesta)), 3)
                self.assertNotContains(respuesta, "boton-curso--activo")

    def test_el_filtro_viejo_por_categoria_no_rompe(self):
        respuesta = self.client.get("/cursos/?categoria=mercancias-peligrosas")
        self.assertEqual(len(self._tarjetas_visibles(respuesta)), 3)

    def test_un_curso_inactivo_no_tiene_boton(self):
        self.assertNotIn(self.oculto.slug, dict(self._botones(self.client.get("/"))))

    def test_un_bloque_sin_cursos_visibles_no_aparece(self):
        self.assertNotContains(self.client.get("/"), "Transporte de Pasajeros")

    def test_el_boton_activo_vuelve_a_mostrar_todo(self):
        respuesta = self.client.get("/?curso=" + self.renovacion.slug)
        self.assertContains(
            respuesta,
            '<a class="boton-curso boton-curso--activo" aria-current="true" '
            'href="/#cursos-lista" data-curso="%s">' % self.renovacion.slug,
        )

    def test_los_botones_no_vuelven_al_principio_de_la_pagina(self):
        respuesta = self.client.get("/cursos/")
        self.assertContains(respuesta, 'id="cursos-lista"')
        self.assertContains(respuesta, "/cursos/?curso=%s#cursos-lista" % self.inicial.slug)
        self.assertContains(respuesta, "js/filtros.js")

    def test_la_pagina_de_cursos_funciona_igual(self):
        respuesta = self.client.get("/cursos/?curso=" + self.inicial.slug)
        self.assertEqual(self._tarjetas_visibles(respuesta), [self.inicial.slug])
