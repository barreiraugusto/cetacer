"""Carga el catálogo real de CETACER y, opcionalmente, datos de ejemplo.

    python manage.py cargar_datos            # catálogo + usuarios de cada rol
    python manage.py cargar_datos --demo     # además, fechas de prueba
"""
import random
from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from contenido.models import EnlacePagina, Pagina
from cuentas.models import Rol, Usuario
from cuentas.permisos import sincronizar_grupos
from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso

CATALOGO = [
    {
        "nombre": "Cargas Generales",
        "orden": 1,
        "resumen": "Cursos para obtener, renovar o ampliar la Licencia Nacional de Conducir profesional.",
        "cursos": [
            {
                "nombre": "Curso primera vez — Cargas Generales",
                "nombre_corto": "Inicial",
                "precio": 405000,
                "requisitos": "Psicofísico vigente, DNI y constancia de pago (e-SICAPRO).",
                "descripcion": (
                    "Curso básico obligatorio para quienes tramitan por primera vez la Licencia "
                    "Nacional Habilitante en las categorías de carga general. Incluye normativa "
                    "vigente, seguridad vial, documentación del transporte y manejo defensivo."
                ),
            },
            {
                "nombre": "Renovación — Cargas Generales y Transporte de Pasajeros",
                "nombre_corto": "Renovación",
                "precio": 115000,
                "requisitos": "Certificado anterior, psicofísico vigente y DNI.",
                "descripcion": "Renovación de la Licencia Nacional Habilitante ya obtenida.",
            },
            {
                "nombre": "Renovación + ampliación — Cargas Generales",
                "nombre_corto": "Ampliación",
                "precio": None,
                "consultar": True,
                "requisitos": "Certificado anterior, psicofísico vigente y DNI.",
                "descripcion": "Renovación de la habilitación vigente sumando una categoría nueva.",
            },
        ],
    },
    {
        "nombre": "Mercancías Peligrosas",
        "orden": 2,
        "resumen": "Certificado obligatorio para el transporte de mercancías y residuos peligrosos.",
        "cursos": [
            {
                "nombre": "Curso primera vez — Mercancías Peligrosas",
                "nombre_corto": "Primera vez",
                "precio": 225000,
                "requisitos": "Licencia profesional vigente, DNI y constancia de pago.",
                "descripcion": (
                    "Habilitación para el transporte de mercancías y residuos peligrosos: "
                    "clasificación de sustancias, rotulado, documentación de porte y "
                    "procedimientos ante incidentes."
                ),
            },
            {
                "nombre": "Curso actualización — Mercancías Peligrosas",
                "nombre_corto": "Renovación",
                "precio": 120000,
                "requisitos": "Certificado anterior de Mercancías Peligrosas y DNI.",
                "descripcion": "Actualización de la habilitación para quienes ya tienen el curso básico aprobado.",
            },
        ],
    },
    {
        "nombre": "Transporte de Pasajeros",
        "orden": 3,
        "resumen": "Habilitación para el transporte de pasajeros.",
        "cursos": [
            {
                "nombre": "Curso primera vez — Transporte de Pasajeros",
                "nombre_corto": "Primera vez",
                "precio": None,
                "consultar": True,
                "requisitos": "Psicofísico vigente y DNI.",
                "descripcion": "Curso básico para quienes tramitan por primera vez la habilitación de pasajeros.",
            },
        ],
    },
]

# Relevado del sitio viejo el 2026-09-15 y depurado: 9 de los 17 enlaces
# originales ya estaban muertos. Ver el spec para el detalle enlace por enlace.
PAGINAS = [
    {
        "titulo": "Legislación",
        "slug": "legislacion",
        "bajada": "Normativa vigente del transporte automotor de cargas.",
        "orden": 1,
        "enlaces": [
            {
                "titulo": "Ley 24449 — Tránsito y Seguridad Vial",
                "descripcion": "Texto actualizado en Infoleg, con las reformas de la Ley 26363.",
                "url": "https://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/818/texact.htm",
                "orden": 1,
            },
            {
                "titulo": "Ley 24449 (PDF)",
                "descripcion": "Copia propia, por si el enlace de Infoleg cambia.",
                "archivo": "documentos/ley-24449-transito.pdf",
                "orden": 2,
            },
            {
                "titulo": "FADEEAC",
                "descripcion": "Departamento de Legislación, Legales y Seguros de la Federación.",
                "url": "https://www.fadeeac.org.ar/departamento-legislacion-legales-y-seguros/",
                "orden": 3,
            },
        ],
    },
    {
        "titulo": "Información útil",
        "slug": "informacion-util",
        "bajada": "Material de interés para la actividad del transportista.",
        "orden": 2,
        "enlaces": [
            {
                "titulo": "Guía del transportista",
                "descripcion": "Documento de FADEEAC, alojado en nuestro sitio.",
                "archivo": "documentos/guia-del-transportista.pdf",
                "grupo": "",
                "orden": 1,
            },
            {
                "titulo": "Vialidad Nacional",
                "url": "https://www.argentina.gob.ar/transporte/vialidad-nacional",
                "grupo": "Organismos",
                "orden": 2,
            },
            {
                "titulo": "Gendarmería Nacional",
                "url": "https://www.argentina.gob.ar/gendarmeria",
                "grupo": "Organismos",
                "orden": 3,
            },
            {
                "titulo": "Registro Automotor",
                "url": "https://www.dnrpa.gov.ar/portal_dnrpa/",
                "grupo": "Organismos",
                "orden": 4,
            },
            {
                "titulo": "Secretaría de Transporte",
                "url": "https://www.argentina.gob.ar/transporte",
                "grupo": "Organismos",
                "orden": 5,
            },
            {
                "titulo": "IRU",
                "descripcion": "International Road Transport Union.",
                "url": "https://www.iru.org/",
                "grupo": "Organismos",
                "orden": 6,
            },
            {
                "titulo": "Consultas sobre multas",
                "url": "https://www.fadeeac.org.ar/consultas-sobre-multas/",
                "grupo": "FADEEAC",
                "orden": 7,
            },
            {
                "titulo": "Estudios económicos y costos",
                "url": "https://www.fadeeac.org.ar/estudios-economicos-y-costos/",
                "grupo": "FADEEAC",
                "orden": 8,
            },
            {
                "titulo": "Otras cámaras",
                "descripcion": "Entidades asociadas a FADEEAC en todo el país.",
                "url": "https://www.fadeeac.org.ar/entidades-asociadas/",
                "grupo": "FADEEAC",
                "orden": 9,
            },
        ],
    },
]

USUARIOS = [
    ("direccion", "Marta", "Gaitán", Rol.DIRECCION, "Gerencia"),
    ("administracion", "Luis", "Peralta", Rol.ADMINISTRACION, "Administración"),
]


class Command(BaseCommand):
    help = "Carga el catálogo de cursos, los roles y usuarios de ejemplo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo", action="store_true",
            help="Agrega fechas de prueba, pasadas y futuras.",
        )
        parser.add_argument(
            "--clave", default="cetacer2024",
            help="Contraseña de los usuarios de ejemplo (por defecto: cetacer2024).",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        random.seed(7)

        self.stdout.write("1/5  Grupos y permisos...")
        sincronizar_grupos()

        self.stdout.write("2/5  Configuración del sitio...")
        ConfiguracionSitio.vigente()

        self.stdout.write("3/5  Catálogo de cursos...")
        cursos_creados = []
        for datos_cat in CATALOGO:
            categoria, _ = Categoria.objects.update_or_create(
                nombre=datos_cat["nombre"],
                defaults={"resumen": datos_cat["resumen"], "orden": datos_cat["orden"], "activa": True},
            )
            for orden, datos_curso in enumerate(datos_cat["cursos"], start=1):
                curso, _ = Curso.objects.update_or_create(
                    nombre=datos_curso["nombre"],
                    defaults={
                        "categoria": categoria,
                        "nombre_corto": datos_curso.get("nombre_corto", ""),
                        "precio": datos_curso["precio"],
                        "precio_a_consultar": datos_curso.get("consultar", False),
                        "requisitos": datos_curso["requisitos"],
                        "descripcion": datos_curso["descripcion"],
                        "orden": orden,
                        "activo": True,
                    },
                )
                cursos_creados.append(curso)

        self.stdout.write("4/5  Usuarios del panel...")
        clave = opciones["clave"]
        for username, nombre, apellido, rol, cargo in USUARIOS:
            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nombre, "last_name": apellido,
                    "email": f"{username}@cetacer.com", "cargo": cargo,
                },
            )
            if creado:
                usuario.set_password(clave)
                usuario.save()
            usuario.asignar_rol(rol)

        self.stdout.write("5/5  Páginas institucionales...")
        self._cargar_paginas()

        if opciones["demo"]:
            self.stdout.write("Extra  Datos de demostración...")
            self._cargar_demo(cursos_creados)

        self.stdout.write(self.style.SUCCESS("\nListo."))
        self.stdout.write(f"  Cursos en el catálogo: {Curso.objects.count()}")
        self.stdout.write(f"  Fechas: {Comision.objects.count()}")
        self.stdout.write(
            f"\n  Usuarios de ejemplo (contraseña «{clave}»): "
            + ", ".join(u[0] for u in USUARIOS)
        )

    def _cargar_paginas(self):
        """Siembra las páginas institucionales, pero sólo si no existen.

        A diferencia del resto del comando, esto NO usa update_or_create con
        defaults: estas páginas están pensadas para que el administrador las
        edite desde el panel (título de un enlace, orden, publicación, etc.),
        y una corrida posterior no debe pisarle esos cambios ni duplicar el
        enlace si le cambió el título. Por eso, una vez creada la página, el
        comando la deja intacta y no vuelve a tocar sus enlaces. El costo es
        que agregar un enlace nuevo a PAGINAS no se propaga a una base ya
        sembrada: hay que cargarlo una vez a mano desde el panel. Es
        deliberado — no lo "arregles" volviendo a update_or_create.
        """
        for datos in PAGINAS:
            pagina, creada = Pagina.objects.get_or_create(
                slug=datos["slug"],
                defaults={
                    "titulo": datos["titulo"],
                    "bajada": datos["bajada"],
                    "orden": datos["orden"],
                    "publicada": True,
                },
            )
            if not creada:
                continue
            for enlace in datos.get("enlaces", []):
                archivo = enlace.get("archivo", "")
                if archivo and not (Path(settings.MEDIA_ROOT) / archivo).exists():
                    # El PDF no está en esta instalación; se sube desde el panel.
                    continue
                EnlacePagina.objects.create(
                    pagina=pagina,
                    titulo=enlace["titulo"],
                    descripcion=enlace.get("descripcion", ""),
                    grupo=enlace.get("grupo", ""),
                    url=enlace.get("url", ""),
                    archivo=archivo,
                    orden=enlace.get("orden", 0),
                    activo=True,
                )

    def _cargar_demo(self, cursos):
        """Fechas pasadas y futuras, con algunas completas y alguna oculta."""
        hoy = date.today()
        for desplazamiento in (-70, -45, -25, -10, 6, 13, 21, 34, 48):
            curso = random.choice(cursos)
            fecha = hoy + timedelta(days=desplazamiento)
            Comision.objects.get_or_create(
                curso=curso,
                fecha_inicio=fecha,
                defaults={
                    "fecha_fin": fecha + timedelta(days=random.choice([0, 0, 1])),
                    "hora_inicio": time(8, 30),
                    "hora_fin": time(16, 30),
                    # Fijas, para que la demo muestre siempre los tres estados.
                    "visible": desplazamiento != 48,
                    "completa": desplazamiento in (-25, 13),
                },
            )
