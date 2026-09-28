"""Filtros de la web pública."""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def buscar_pagina(paginas, slug):
    """Busca una página por slug en el dict del contexto.

    Hace falta porque los slugs con guión (`informacion-util`) no se pueden
    buscar con la notación de punto de las plantillas.
    """
    return (paginas or {}).get(slug)


# Direcciones escritas a mano: con esquema o arrancando por www.
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
# Dos o más mayúsculas seguidas, y las palabras en mayúscula que las continúan:
# «LICENCIA DE CONDUCIR» se resalta entera, la «Y» suelta de una frase no.
_MAYUSCULAS = re.compile(
    r"(?<!\w)[A-ZÁÉÍÓÚÜÑ]{2,}(?:[ \t]+[A-ZÁÉÍÓÚÜÑ]+)*(?![\w])"
)


def _resaltar(texto):
    return _MAYUSCULAS.sub(lambda m: f"<strong>{m.group(0)}</strong>", escape(texto))


def _enlace(url):
    # La puntuación que cierra la oración no es parte de la dirección.
    sobrante = ""
    while url and url[-1] in ".,;:)!?":
        sobrante = url[-1] + sobrante
        url = url[:-1]
    destino = url if url.lower().startswith("http") else f"https://{url}"
    return (
        f'<a href="{escape(destino)}" rel="noopener" target="_blank">{escape(url)}</a>'
        + escape(sobrante)
    )


@register.filter
def texto_curso(texto):
    """Formatea los textos libres del curso: enlaces y mayúsculas en negrita.

    Se usa en la descripción y en los requisitos. Quien carga los cursos
    escribe en mayúsculas lo importante («Foto DNI»,
    «LICENCIA DE CONDUCIR»); acá eso se pasa a negrita y las direcciones se
    vuelven enlaces. Todo lo demás se escapa, así que el texto sigue sin
    admitir HTML propio.
    """
    partes = []
    ultimo = 0
    for coincidencia in _URL.finditer(texto or ""):
        partes.append(_resaltar(texto[ultimo:coincidencia.start()]))
        partes.append(_enlace(coincidencia.group(0)))
        ultimo = coincidencia.end()
    partes.append(_resaltar((texto or "")[ultimo:]))
    return mark_safe("".join(partes).replace("\r\n", "\n").replace("\n", "<br>"))
