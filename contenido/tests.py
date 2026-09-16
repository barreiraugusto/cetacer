"""Pruebas de las páginas de contenido institucional."""
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from contenido.models import EnlacePagina, Pagina
from cuentas.models import Rol, Usuario


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


class PaginaPublicaTests(TestCase):
    def setUp(self):
        self.pagina = Pagina.objects.create(
            titulo="Legislación", bajada="Normativa vigente."
        )
        EnlacePagina.objects.create(
            pagina=self.pagina, titulo="Ley 24449", url="https://ejemplo.test/ley",
            grupo="Leyes",
        )

    def test_url_propia(self):
        self.assertEqual(self.pagina.get_absolute_url(), "/info/legislacion/")

    def test_la_pagina_publicada_se_ve(self):
        respuesta = self.client.get("/info/legislacion/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Normativa vigente.")
        self.assertContains(respuesta, "Ley 24449")
        self.assertContains(respuesta, "Leyes")

    def test_la_pagina_despublicada_da_404(self):
        self.pagina.publicada = False
        self.pagina.save()
        self.assertEqual(self.client.get("/info/legislacion/").status_code, 404)

    def test_un_slug_inexistente_da_404(self):
        self.assertEqual(self.client.get("/info/no-existe/").status_code, 404)

    def test_las_paginas_publicadas_estan_en_el_contexto(self):
        respuesta = self.client.get("/")
        self.assertIn("legislacion", respuesta.context["paginas"])

    def test_las_despublicadas_no_estan_en_el_contexto(self):
        self.pagina.publicada = False
        self.pagina.save()
        respuesta = self.client.get("/")
        self.assertNotIn("legislacion", respuesta.context["paginas"])

    def test_el_contexto_aguanta_que_la_tabla_no_exista(self):
        # Pasa de verdad en una base recién creada, antes de migrar.
        from unittest.mock import patch

        from django.db.utils import OperationalError

        from web.context_processors import paginas_de_contenido

        with patch.object(Pagina, "publicadas", side_effect=OperationalError("no such table")):
            self.assertEqual(paginas_de_contenido(None), {"paginas": {}})


class SinEnlacesAlDominioViejoTests(SimpleTestCase):
    """El bug que este trabajo arregla: que una plantilla saque al visitante
    hacia el dominio que se da de baja."""

    def test_ninguna_plantilla_enlaza_al_dominio_viejo(self):
        raiz = Path(settings.BASE_DIR) / "templates"
        ofensores = []
        for plantilla in raiz.rglob("*.html"):
            texto = plantilla.read_text(encoding="utf-8")
            if re.search(r'href="https?://(www\.)?cetacer\.com', texto):
                ofensores.append(str(plantilla.relative_to(raiz)))
        self.assertEqual(
            ofensores, [],
            "Estas plantillas enlazan al dominio viejo: " + ", ".join(ofensores),
        )


class TarjetasDelInicioTests(TestCase):
    def test_la_tarjeta_enlaza_a_la_pagina_interna(self):
        Pagina.objects.create(titulo="Legislación")
        respuesta = self.client.get("/")
        self.assertContains(respuesta, 'href="/info/legislacion/"')

    def test_sin_pagina_cargada_la_tarjeta_no_muestra_enlace(self):
        respuesta = self.client.get("/")
        self.assertNotContains(respuesta, "Ver legislación")

    def test_la_pagina_despublicada_no_se_enlaza(self):
        Pagina.objects.create(titulo="Legislación", publicada=False)
        respuesta = self.client.get("/")
        self.assertNotContains(respuesta, 'href="/info/legislacion/"')

    def test_la_tarjeta_con_slug_con_guion_tambien_enlaza(self):
        # `informacion-util` es el caso que justifica el filtro `buscar_pagina`:
        # con notación de punto la plantilla renderizaría vacío sin avisar.
        Pagina.objects.create(titulo="Información útil")
        respuesta = self.client.get("/")
        self.assertContains(respuesta, 'href="/info/informacion-util/"')


class PanelPaginasTests(TestCase):
    def setUp(self):
        self.pagina = Pagina.objects.create(titulo="Legislación")

    def _usuario(self, username, rol):
        # `Usuario.rol` es una property derivada de los grupos: se asigna con
        # `asignar_rol()`, no por atributo.
        usuario = Usuario.objects.create_user(username=username, password="clave-de-prueba")
        usuario.asignar_rol(rol)
        return usuario

    def test_administracion_entra_al_listado(self):
        self._usuario("admin_test", Rol.ADMINISTRACION)
        self.client.login(username="admin_test", password="clave-de-prueba")
        respuesta = self.client.get("/panel/paginas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Legislación")

    def test_recepcion_no_entra(self):
        self._usuario("recepcion_test", Rol.RECEPCION)
        self.client.login(username="recepcion_test", password="clave-de-prueba")
        respuesta = self.client.get("/panel/paginas/")
        self.assertEqual(respuesta.status_code, 302)

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get("/panel/paginas/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/panel/ingresar/", respuesta["Location"])

    def test_crear_una_pagina_con_sus_enlaces(self):
        self._usuario("admin_test", Rol.ADMINISTRACION)
        self.client.login(username="admin_test", password="clave-de-prueba")
        respuesta = self.client.post("/panel/paginas/nueva/", {
            "titulo": "Información útil",
            "bajada": "Material de interés.",
            "orden": 0,
            "publicada": "on",
            "enlaces-TOTAL_FORMS": "1",
            "enlaces-INITIAL_FORMS": "0",
            "enlaces-MIN_NUM_FORMS": "0",
            "enlaces-MAX_NUM_FORMS": "1000",
            "enlaces-0-titulo": "IRU",
            "enlaces-0-descripcion": "",
            "enlaces-0-grupo": "Organismos",
            "enlaces-0-url": "https://www.iru.org/",
            "enlaces-0-orden": "0",
            "enlaces-0-activo": "on",
        })
        self.assertEqual(respuesta.status_code, 302)
        creada = Pagina.objects.get(slug="informacion-util")
        self.assertEqual(creada.enlaces.count(), 1)
        self.assertEqual(creada.enlaces.first().grupo, "Organismos")

    def test_una_pagina_con_un_enlace_invalido_no_se_guarda(self):
        self._usuario("admin_test", Rol.ADMINISTRACION)
        self.client.login(username="admin_test", password="clave-de-prueba")
        respuesta = self.client.post("/panel/paginas/nueva/", {
            "titulo": "Rota",
            "orden": 0,
            "enlaces-TOTAL_FORMS": "1",
            "enlaces-INITIAL_FORMS": "0",
            "enlaces-MIN_NUM_FORMS": "0",
            "enlaces-MAX_NUM_FORMS": "1000",
            "enlaces-0-titulo": "Sin destino",
            "enlaces-0-descripcion": "",
            "enlaces-0-grupo": "",
            "enlaces-0-url": "",
            "enlaces-0-orden": "0",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Pagina.objects.filter(titulo="Rota").exists())

    def test_las_filas_extra_vacias_del_formset_no_molestan(self):
        # `/panel/paginas/nueva/` renderiza el formset con `extra=3`: un
        # navegador real manda las tres filas aunque sólo se complete una.
        # Las filas vacías llegan con los valores por defecto que el propio
        # formulario les puso (`orden=0`, `activo` tildado).
        self._usuario("admin_test", Rol.ADMINISTRACION)
        self.client.login(username="admin_test", password="clave-de-prueba")
        respuesta = self.client.post("/panel/paginas/nueva/", {
            "titulo": "Información útil",
            "bajada": "Material de interés.",
            "orden": 0,
            "publicada": "on",
            "enlaces-TOTAL_FORMS": "3",
            "enlaces-INITIAL_FORMS": "0",
            "enlaces-MIN_NUM_FORMS": "0",
            "enlaces-MAX_NUM_FORMS": "1000",
            "enlaces-0-titulo": "IRU",
            "enlaces-0-descripcion": "",
            "enlaces-0-grupo": "Organismos",
            "enlaces-0-url": "https://www.iru.org/",
            "enlaces-0-orden": "0",
            "enlaces-0-activo": "on",
            "enlaces-1-titulo": "",
            "enlaces-1-descripcion": "",
            "enlaces-1-grupo": "",
            "enlaces-1-url": "",
            "enlaces-1-orden": "0",
            "enlaces-1-activo": "on",
            "enlaces-2-titulo": "",
            "enlaces-2-descripcion": "",
            "enlaces-2-grupo": "",
            "enlaces-2-url": "",
            "enlaces-2-orden": "0",
            "enlaces-2-activo": "on",
        })
        self.assertEqual(respuesta.status_code, 302)
        creada = Pagina.objects.get(slug="informacion-util")
        self.assertEqual(creada.enlaces.count(), 1)

    def test_un_get_no_borra_la_pagina(self):
        self._usuario("admin_test", Rol.ADMINISTRACION)
        self.client.login(username="admin_test", password="clave-de-prueba")
        respuesta = self.client.get(f"/panel/paginas/{self.pagina.pk}/eliminar/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Pagina.objects.filter(pk=self.pagina.pk).exists())

    def test_un_post_si_borra_la_pagina(self):
        self._usuario("admin_test", Rol.ADMINISTRACION)
        self.client.login(username="admin_test", password="clave-de-prueba")
        respuesta = self.client.post(f"/panel/paginas/{self.pagina.pk}/eliminar/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Pagina.objects.filter(pk=self.pagina.pk).exists())


class CargarPaginasTests(TestCase):
    def test_el_comando_crea_las_dos_paginas(self):
        call_command("cargar_datos", verbosity=0)
        self.assertTrue(Pagina.objects.filter(slug="legislacion").exists())
        self.assertTrue(Pagina.objects.filter(slug="informacion-util").exists())

    def test_los_enlaces_cargados_estan_vivos_segun_el_relevamiento(self):
        call_command("cargar_datos", verbosity=0)
        info = Pagina.objects.get(slug="informacion-util")
        titulos = [e.titulo for e in info.enlaces.all()]
        self.assertIn("Gendarmería Nacional", titulos)
        self.assertNotIn("Occovi", titulos)  # organismo disuelto

    def test_es_idempotente(self):
        call_command("cargar_datos", verbosity=0)
        call_command("cargar_datos", verbosity=0)
        self.assertEqual(Pagina.objects.filter(slug="legislacion").count(), 1)
        legislacion = Pagina.objects.get(slug="legislacion")
        self.assertEqual(
            legislacion.enlaces.filter(titulo="Ley 24449 — Tránsito y Seguridad Vial").count(), 1
        )
        self.assertEqual(legislacion.enlaces.count(), 3)
        informacion_util = Pagina.objects.get(slug="informacion-util")
        self.assertEqual(informacion_util.enlaces.count(), 8)

    def test_no_duplica_ni_pisa_lo_que_editó_el_administrador(self):
        call_command("cargar_datos", verbosity=0)
        legislacion = Pagina.objects.get(slug="legislacion")
        enlace = legislacion.enlaces.get(titulo="FADEEAC")
        enlace.titulo = "Federación Argentina (FADEEAC)"
        enlace.save()
        legislacion.publicada = False
        legislacion.save()

        call_command("cargar_datos", verbosity=0)

        legislacion.refresh_from_db()
        self.assertEqual(legislacion.enlaces.count(), 3)
        self.assertTrue(legislacion.enlaces.filter(titulo="Federación Argentina (FADEEAC)").exists())
        self.assertFalse(legislacion.publicada)
