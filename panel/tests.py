"""Pruebas del panel: manual de uso y administración de usuarios."""
import re
from datetime import date

from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from cuentas.models import JERARQUIA, Rol, Usuario
from cuentas.permisos import sincronizar_grupos
from cursos.models import Categoria, Comision, Curso

CAPITULOS = ["ingresar", "agenda", "cursos", "fechas", "paginas", "administracion", "referencia"]


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
        self.assertGreater(len(capturas), 10)
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
        cls.recepcion = cls._crear("diego", Rol.ADMINISTRACION)

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


class FechasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.direccion = Usuario.objects.create_user(username="marta", password="clave-larga-123")
        cls.direccion.asignar_rol(Rol.DIRECCION)
        categoria = Categoria.objects.create(nombre="Cargas Generales")
        cls.curso = Curso.objects.create(categoria=categoria, nombre="Inicial", precio=1)
        cls.fecha = Comision.objects.create(
            curso=cls.curso, fecha_inicio=date(2030, 3, 5), fecha_fin=date(2030, 3, 7)
        )

    def setUp(self):
        self.client.force_login(self.direccion)

    def test_una_fecha_nueva_queda_publicada(self):
        self.client.post(reverse("panel:fecha_nueva"), {
            "curso": self.curso.pk, "fecha_inicio": "2030-05-10", "visible": "on",
        })
        nueva = Comision.objects.get(fecha_inicio=date(2030, 5, 10))
        self.assertTrue(nueva.visible)
        self.assertFalse(nueva.completa)

    def test_el_formulario_nuevo_trae_visible_tildado(self):
        formulario = self.client.get(reverse("panel:fecha_nueva")).context["form"]
        self.assertTrue(formulario["visible"].value())
        self.assertFalse(formulario["completa"].value())

    def test_agregar_fecha_desde_un_curso_lo_trae_elegido(self):
        url = reverse("panel:fecha_nueva") + f"?curso={self.curso.pk}"
        self.assertEqual(self.client.get(url).context["form"]["curso"].value(), self.curso.pk)
        # Un curso que no existe, o un valor cualquiera, no rompe el formulario.
        for valor in ("9999", "abc", ""):
            with self.subTest(curso=valor):
                url = reverse("panel:fecha_nueva") + f"?curso={valor}"
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_el_formulario_trae_las_fechas_cargadas(self):
        respuesta = self.client.get(reverse("panel:fecha_editar", args=[self.fecha.pk]))
        self.assertContains(respuesta, 'value="2030-03-05"')
        self.assertContains(respuesta, 'value="2030-03-07"')

    def test_marcar_completa_y_volver_a_disponible(self):
        url = reverse("panel:fecha_marcar", args=[self.fecha.pk])
        self.client.post(url, {"campo": "completa", "valor": "1"})
        self.fecha.refresh_from_db()
        self.assertTrue(self.fecha.completa)
        self.client.post(url, {"campo": "completa", "valor": "0"})
        self.fecha.refresh_from_db()
        self.assertFalse(self.fecha.completa)

    def test_ocultar_y_publicar(self):
        url = reverse("panel:fecha_marcar", args=[self.fecha.pk])
        self.client.post(url, {"campo": "visible", "valor": "0"})
        self.fecha.refresh_from_db()
        self.assertFalse(self.fecha.visible)
        self.client.post(url, {"campo": "visible", "valor": "1"})
        self.fecha.refresh_from_db()
        self.assertTrue(self.fecha.visible)

    def test_marcar_no_acepta_otros_campos_ni_get(self):
        url = reverse("panel:fecha_marcar", args=[self.fecha.pk])
        self.client.post(url, {"campo": "curso", "valor": "1"})
        self.client.get(url)
        self.fecha.refresh_from_db()
        self.assertTrue(self.fecha.visible)
        self.assertFalse(self.fecha.completa)

    def test_marcar_vuelve_a_donde_estaba(self):
        respuesta = self.client.post(
            reverse("panel:fecha_marcar", args=[self.fecha.pk]),
            {"campo": "completa", "valor": "1", "next": reverse("panel:inicio")},
        )
        self.assertRedirects(respuesta, reverse("panel:inicio"))

    def test_marcar_no_redirige_afuera(self):
        respuesta = self.client.post(
            reverse("panel:fecha_marcar", args=[self.fecha.pk]),
            {"campo": "completa", "valor": "1", "next": "https://ejemplo.com/"},
        )
        self.assertRedirects(respuesta, reverse("panel:fechas"))

    def test_el_listado_y_el_tablero_ofrecen_las_acciones_rapidas(self):
        for nombre in ("panel:fechas", "panel:inicio"):
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertContains(respuesta, "Marcar completa")
                self.assertContains(respuesta, "Ocultar")
        self.fecha.completa = True
        self.fecha.visible = False
        self.fecha.save()
        respuesta = self.client.get(reverse("panel:fechas"))
        self.assertContains(respuesta, "Marcar disponible")
        self.assertContains(respuesta, "Publicar")

    def test_se_elimina_con_post_y_no_con_get(self):
        url = reverse("panel:fecha_eliminar", args=[self.fecha.pk])
        self.client.get(url)
        self.assertTrue(Comision.objects.filter(pk=self.fecha.pk).exists())
        self.client.post(url)
        self.assertFalse(Comision.objects.filter(pk=self.fecha.pk).exists())

    def test_el_listado_ordena_por_fecha_y_separa_las_pasadas(self):
        pasada = Comision.objects.create(curso=self.curso, fecha_inicio=date(2020, 1, 1))
        antes = Comision.objects.create(curso=self.curso, fecha_inicio=date(2030, 1, 1))
        proximas = list(self.client.get(reverse("panel:fechas")).context["fechas"])
        self.assertEqual(proximas, [antes, self.fecha])
        pasadas = self.client.get(reverse("panel:fechas") + "?cuando=pasadas").context["fechas"]
        self.assertEqual(list(pasadas), [pasada])

    def test_una_fecha_de_fin_anterior_al_inicio_no_se_guarda(self):
        respuesta = self.client.post(reverse("panel:fecha_nueva"), {
            "curso": self.curso.pk, "fecha_inicio": "2030-05-10", "fecha_fin": "2030-05-09",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "campo-fila--error")
        self.assertFalse(Comision.objects.filter(fecha_inicio=date(2030, 5, 10)).exists())

    def test_los_enlaces_viejos_dan_404(self):
        for ruta in ("comisiones/", f"comisiones/{self.fecha.pk}/", "comisiones/nueva/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(f"/panel/{ruta}").status_code, 404)

    def test_nada_dice_comision(self):
        pantallas = [reverse(n) for n in (
            "panel:inicio", "panel:fechas", "panel:fecha_nueva", "panel:agenda",
            "panel:cursos", "panel:curso_nuevo", "panel:usuarios", "panel:configuracion",
        )]
        pantallas.append(reverse("panel:fecha_editar", args=[self.fecha.pk]))
        pantallas.append(reverse("panel:curso_editar", args=[self.curso.pk]))
        for url in pantallas:
            with self.subTest(pantalla=url):
                html = self.client.get(url).content.decode().lower()
                self.assertNotIn("comisi", html)
                self.assertNotIn("cupo", html)

    def test_el_tablero_cuenta_publicadas_completas_y_ocultas(self):
        Comision.objects.create(curso=self.curso, fecha_inicio=date(2030, 6, 1), completa=True)
        Comision.objects.create(curso=self.curso, fecha_inicio=date(2030, 6, 2), visible=False)
        Comision.objects.create(curso=self.curso, fecha_inicio=date(2020, 1, 1))
        indicadores = self.client.get(reverse("panel:inicio")).context["indicadores"]
        self.assertEqual(indicadores, {"publicadas": 2, "completas": 1, "ocultas": 1})

    def test_la_agenda_muestra_la_fecha_con_el_color_de_su_estado(self):
        respuesta = self.client.get(reverse("panel:agenda") + "?anio=2030&mes=3")
        self.assertContains(respuesta, "calendario__evento--disponible")
        self.assertContains(respuesta, reverse("panel:fecha_editar", args=[self.fecha.pk]))


class PanelSinPersonasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.direccion = Usuario.objects.create_user(username="marta", password="clave-larga-123")
        cls.direccion.asignar_rol(Rol.DIRECCION)

    def setUp(self):
        self.client.force_login(self.direccion)

    def test_las_pantallas_de_personas_ya_no_existen(self):
        for ruta in ("inscripciones/", "participantes/", "empresas/", "informes/",
                     "inscripciones/exportar/", "participantes/nuevo/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(f"/panel/{ruta}").status_code, 404)

    def test_el_menu_no_las_ofrece(self):
        respuesta = self.client.get(reverse("panel:inicio"))
        for texto in ("Inscripciones", "Participantes", "Informes", "PERSONAS"):
            self.assertNotContains(respuesta, texto)

    def test_el_tablero_no_habla_de_inscriptos_ni_pagos(self):
        respuesta = self.client.get(reverse("panel:inicio"))
        for texto in ("INSCRIPTOS", "PAGOS PENDIENTES", "SOLICITUDES WEB", "Últimas inscripciones"):
            self.assertNotContains(respuesta, texto)


class PermisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.administracion = Usuario.objects.create_user(username="luis", password="clave-larga-123")
        cls.administracion.asignar_rol(Rol.ADMINISTRACION)
        cls.sin_rol = Usuario.objects.create_user(username="viejo", password="clave-larga-123")
        categoria = Categoria.objects.create(nombre="Cargas Generales")
        curso = Curso.objects.create(categoria=categoria, nombre="Inicial", precio=1)
        cls.fecha = Comision.objects.create(curso=curso, fecha_inicio=date(2030, 3, 5))

    def test_administracion_gestiona_fechas_cursos_y_paginas(self):
        self.client.force_login(self.administracion)
        for nombre in ("panel:inicio", "panel:agenda", "panel:fechas", "panel:fecha_nueva",
                       "panel:cursos", "panel:curso_nuevo", "panel:categorias",
                       "panel:categoria_nueva", "panel:paginas", "panel:pagina_nueva", "panel:ayuda"):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_administracion_marca_una_fecha_como_completa(self):
        self.client.force_login(self.administracion)
        self.client.post(
            reverse("panel:fecha_marcar", args=[self.fecha.pk]), {"campo": "completa", "valor": "1"}
        )
        self.fecha.refresh_from_db()
        self.assertTrue(self.fecha.completa)

    def test_administracion_no_toca_usuarios_ni_configuracion(self):
        self.client.force_login(self.administracion)
        for nombre in ("panel:usuarios", "panel:usuario_nuevo", "panel:configuracion"):
            with self.subTest(pantalla=nombre):
                self.assertRedirects(self.client.get(reverse(nombre)), reverse("panel:inicio"))

    def test_el_menu_de_administracion_no_ofrece_usuarios_ni_configuracion(self):
        self.client.force_login(self.administracion)
        respuesta = self.client.get(reverse("panel:inicio"))
        self.assertNotContains(respuesta, "Usuarios y permisos")
        self.assertNotContains(respuesta, reverse("panel:configuracion"))
        self.assertContains(respuesta, reverse("panel:paginas"))

    def test_un_usuario_sin_rol_no_entra_y_no_rompe(self):
        self.client.force_login(self.sin_rol)
        for nombre in ("panel:inicio", "panel:fechas", "panel:ayuda"):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_un_usuario_sin_rol_no_puede_cambiar_una_fecha(self):
        self.client.force_login(self.sin_rol)
        self.client.post(
            reverse("panel:fecha_marcar", args=[self.fecha.pk]), {"campo": "completa", "valor": "1"}
        )
        self.fecha.refresh_from_db()
        self.assertFalse(self.fecha.completa)
