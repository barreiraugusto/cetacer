"""Filtros de la web pública."""
from django import template

register = template.Library()


@register.filter
def buscar_pagina(paginas, slug):
    """Busca una página por slug en el dict del contexto.

    Hace falta porque los slugs con guión (`informacion-util`) no se pueden
    buscar con la notación de punto de las plantillas.
    """
    return (paginas or {}).get(slug)
