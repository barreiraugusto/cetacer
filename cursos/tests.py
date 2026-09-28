"""Pruebas del catálogo, las comisiones y el cupo."""
from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso, ImagenPortada
from inscripciones.models import Inscripcion, Participante


class CursoTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Cargas Generales")
        self.curso = Curso.objects.create(
            categoria=self.categoria, nombre="Curso primera vez", precio=405000
        )

    def test_el_slug_se_genera_solo(self):
        self.assertEqual(self.curso.slug, "curso-primera-vez")

    def test_los_slugs_repetidos_reciben_sufijo(self):
        otro = Curso.objects.create(categoria=self.categoria, nombre="Curso primera vez")
        self.assertEqual(otro.slug, "curso-primera-vez-2")

    def test_precio_texto_usa_separador_de_miles(self):
        self.assertEqual(self.curso.precio_texto, "$405.000")

    def test_precio_a_consultar(self):
        self.curso.precio_a_consultar = True
        self.assertEqual(self.curso.precio_texto, "Consultar")

    def test_sin_precio_muestra_consultar(self):
        sin_precio = Curso.objects.create(categoria=self.categoria, nombre="Otro")
        self.assertEqual(sin_precio.precio_texto, "Consultar")

    def test_conteo_de_la_categoria(self):
        self.assertEqual(self.categoria.conteo_texto, "1 curso")
        Curso.objects.create(categoria=self.categoria, nombre="Segundo")
        self.assertEqual(self.categoria.conteo_texto, "2 cursos")


class ComisionTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nombre="Cargas")
        self.curso = Curso.objects.create(categoria=categoria, nombre="Básico", precio=1000)
        self.comision = Comision.objects.create(
            curso=self.curso,
            fecha_inicio=date.today() + timedelta(days=10),
            hora_inicio=time(8, 30),
            hora_fin=time(16, 30),
            cupo=3,
            estado=Comision.Estado.PUBLICADA,
        )

    def _inscribir(self, dni, estado=Inscripcion.Estado.CONFIRMADA):
        participante = Participante.objects.create(dni=dni, apellido="Test", nombre=dni)
        return Inscripcion.objects.create(
            comision=self.comision, participante=participante, estado=estado
        )

    def test_cupo_disponible(self):
        self.assertEqual(self.comision.lugares_disponibles, 3)
        self._inscribir("10000001")
        self.assertEqual(self.comision.lugares_disponibles, 2)

    def test_las_canceladas_no_ocupan_cupo(self):
        self._inscribir("10000001", Inscripcion.Estado.CANCELADA)
        self.assertEqual(self.comision.cantidad_inscriptos, 0)
        self.assertEqual(self.comision.lugares_disponibles, 3)

    def test_completa_al_llegar_al_cupo(self):
        for dni in ("10000001", "10000002", "10000003"):
            self._inscribir(dni)
        self.assertTrue(self.comision.completa)
        self.assertEqual(self.comision.ocupacion_porcentaje, 100)
        self.assertEqual(self.comision.semaforo, "completa")

    def test_horario_texto(self):
        self.assertEqual(self.comision.horario_texto, "08:30 a 16:30 h")

    def test_horario_cae_al_texto_del_curso_si_no_hay_horas(self):
        self.comision.hora_inicio = self.comision.hora_fin = None
        self.assertEqual(self.comision.horario_texto, self.curso.duracion_horario)

    def test_solo_las_publicadas_futuras_salen_en_la_web(self):
        self.assertIn(self.comision, self.curso.comisiones_publicadas())
        self.comision.estado = Comision.Estado.BORRADOR
        self.comision.save()
        self.assertNotIn(self.comision, self.curso.comisiones_publicadas())

    def test_las_pasadas_no_salen_en_la_web(self):
        self.comision.fecha_inicio = date.today() - timedelta(days=1)
        self.comision.save()
        self.assertNotIn(self.comision, self.curso.comisiones_publicadas())

    def test_lugar_cae_a_la_sede_configurada(self):
        self.assertEqual(self.comision.lugar_texto, ConfiguracionSitio.vigente().direccion)


class FechaTextoTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nombre="Cargas")
        self.curso = Curso.objects.create(categoria=categoria, nombre="Básico")

    def _texto(self, inicio, fin=None):
        return Comision(curso=self.curso, fecha_inicio=inicio, fecha_fin=fin).fecha_texto

    def test_un_solo_dia(self):
        self.assertEqual(self._texto(date(2026, 10, 5)), "5 de octubre")

    def test_en_el_mismo_mes_no_repite_el_mes(self):
        self.assertEqual(
            self._texto(date(2026, 10, 5), date(2026, 10, 7)), "5 al 7 de octubre"
        )

    def test_entre_dos_meses_nombra_los_dos(self):
        self.assertEqual(
            self._texto(date(2026, 9, 30), date(2026, 10, 2)),
            "30 de setiembre al 2 de octubre",
        )

    def test_mismo_dia_de_inicio_y_fin(self):
        self.assertEqual(self._texto(date(2026, 10, 5), date(2026, 10, 5)), "5 de octubre")


class ConfiguracionTests(TestCase):
    def test_vigente_es_singleton(self):
        primera = ConfiguracionSitio.vigente()
        self.assertEqual(ConfiguracionSitio.vigente().pk, primera.pk)
        self.assertEqual(ConfiguracionSitio.objects.count(), 1)

    def test_enlace_whatsapp_escapa_el_texto(self):
        sitio = ConfiguracionSitio.vigente()
        enlace = sitio.enlace_whatsapp("Hola, ¿turno?")
        self.assertTrue(enlace.startswith(f"https://wa.me/{sitio.whatsapp}?text="))
        self.assertNotIn(" ", enlace)

    def test_whatsapp_de_socios_sin_el_cero_y_con_el_codigo_de_pais(self):
        sitio = ConfiguracionSitio(whatsapp_socios="(0343) 4503288")
        self.assertEqual(sitio.whatsapp_socios_url, "https://wa.me/543434503288")

    def test_sin_whatsapp_de_socios_no_hay_enlace(self):
        self.assertEqual(ConfiguracionSitio(whatsapp_socios="").whatsapp_socios_url, "")

    def test_video_de_cursos_en_sus_distintas_formas(self):
        embed = "https://www.youtube-nocookie.com/embed/0YY-WsyDzD8"
        for url in (
            "https://www.youtube.com/watch?v=0YY-WsyDzD8",
            "https://youtube.com/watch?v=0YY-WsyDzD8&t=12s",
            "https://youtu.be/0YY-WsyDzD8",
            "https://www.youtube.com/embed/0YY-WsyDzD8",
            "https://www.youtube.com/shorts/0YY-WsyDzD8",
        ):
            with self.subTest(url=url):
                self.assertEqual(ConfiguracionSitio(video_cursos=url).video_cursos_embed, embed)

    def test_un_video_que_no_es_de_youtube_no_se_embebe(self):
        for url in ("", "https://vimeo.com/123456", "https://www.youtube.com/watch?v=<script>"):
            with self.subTest(url=url):
                self.assertEqual(ConfiguracionSitio(video_cursos=url).video_cursos_embed, "")


class FormasDePagoTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Cargas Generales")
        self.curso = Curso.objects.create(
            categoria=self.categoria, nombre="Curso primera vez", precio=405000
        )

    def test_la_configuracion_trae_el_alias_por_defecto(self):
        sitio = ConfiguracionSitio.vigente()
        self.assertEqual(sitio.pago_alias, "FPT.LICENCIAPROF")
        self.assertEqual(sitio.pago_banco, "Banco Nación")

    def test_la_ficha_del_curso_muestra_el_alias(self):
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertContains(respuesta, "FPT.LICENCIAPROF")

    def test_sin_alias_no_se_muestra_el_bloque(self):
        sitio = ConfiguracionSitio.vigente()
        sitio.pago_alias = ""
        sitio.pago_banco = ""
        sitio.pago_titular = ""
        sitio.pago_aclaracion = ""
        sitio.save()
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertNotContains(respuesta, "FORMAS DE PAGO")

    def test_con_solo_el_titular_cargado_el_bloque_igual_se_muestra(self):
        sitio = ConfiguracionSitio.vigente()
        sitio.pago_alias = ""
        sitio.pago_banco = ""
        sitio.pago_aclaracion = ""
        sitio.pago_titular = "Cámara Empresaria del Transporte"
        sitio.save()
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertContains(respuesta, "FORMAS DE PAGO")
        self.assertContains(respuesta, "Cámara Empresaria del Transporte")

    def test_el_curso_ya_no_tiene_link_externo(self):
        self.assertFalse(hasattr(self.curso, "link_externo"))


class IconoCategoriaTests(TestCase):
    """CETACER pidió poder ponerle un icono a cada categoría (los mandan aparte)."""

    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Cargas Generales")
        Curso.objects.create(categoria=self.categoria, nombre="Básico", precio=1000)

    def test_sin_icono_la_web_no_dibuja_la_imagen(self):
        html = self.client.get(reverse("web:inicio")).content.decode()
        self.assertNotIn("categoria__icono", html)

    def test_con_icono_la_web_lo_muestra_junto_al_titulo(self):
        self.categoria.icono = SimpleUploadedFile(
            "cargas.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            content_type="image/svg+xml",
        )
        self.categoria.save()
        self.addCleanup(self.categoria.icono.delete, save=False)

        html = self.client.get(reverse("web:inicio")).content.decode()
        self.assertIn("categoria__icono", html)
        self.assertIn(self.categoria.icono.url, html)
        # Decorativo: el nombre ya va en el h3, el icono no lo repite.
        self.assertIn('alt=""', html)

    def test_solo_acepta_formatos_de_icono(self):
        categoria = Categoria(nombre="Otra")
        categoria.icono = SimpleUploadedFile("icono.exe", b"MZ", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError):
            categoria.full_clean()


class PortadaTests(TestCase):
    """La portada tiene que poder rotar entre varias fotos (punto 21 del pedido)."""

    def setUp(self):
        self.sitio = ConfiguracionSitio.vigente()

    def _foto(self, nombre, orden=0, activa=True):
        imagen = ImagenPortada.objects.create(
            sitio=self.sitio, orden=orden, activa=activa,
            imagen=SimpleUploadedFile(nombre, b"\xff\xd8\xff", content_type="image/jpeg"),
        )
        self.addCleanup(imagen.imagen.delete, save=False)
        return imagen

    def test_sin_fotos_cargadas_cae_en_la_del_camion(self):
        html = self.client.get(reverse("web:inicio")).content.decode()
        self.assertIn("portada-camion", html)
        self.assertIn("portada__foto--activa", html)

    def test_una_sola_foto_no_carga_el_script_de_rotacion(self):
        self._foto("camara.jpg")
        html = self.client.get(reverse("web:inicio")).content.decode()
        self.assertNotIn("portada-camion", html)
        self.assertNotIn("js/portada.js", html)

    def test_dos_fotos_rotan_y_solo_una_arranca_visible(self):
        self._foto("camion.jpg", orden=1)
        self._foto("camara.jpg", orden=2)
        html = self.client.get(reverse("web:inicio")).content.decode()
        self.assertIn("js/portada.js", html)
        self.assertEqual(html.count("portada__foto--activa"), 1)
        self.assertEqual(html.count('class="portada__foto'), 2)

    def test_las_fotos_apagadas_no_salen(self):
        self._foto("visible.jpg", orden=1)
        self._foto("oculta.jpg", orden=2, activa=False)
        self.assertEqual(self.sitio.portada_visible.count(), 1)

    def test_se_respeta_el_orden(self):
        segunda = self._foto("b.jpg", orden=2)
        primera = self._foto("a.jpg", orden=1)
        self.assertEqual(
            list(self.sitio.portada_visible), [primera, segunda]
        )
