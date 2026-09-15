"""Filtros de plantilla propios del panel."""
from django import template

register = template.Library()

#: Palabras cuyo plural en español no se arma agregando una letra.
#: Las terminadas en -ón pierden la tilde: comisión → comisiones.
PLURALES = {
    "comisión": "comisiones",
    "inscripción": "inscripciones",
    "capacitación": "capacitaciones",
}


@register.filter
def plural(cantidad, palabra):
    """Devuelve la palabra en singular o plural según la cantidad.

    El filtro `pluralize` de Django agrega letras al final, y en español eso
    rompe las palabras con tilde en la última sílaba («comisiónes»). Este filtro
    usa la forma correcta.

        {{ total }} {{ total|plural:"comisión" }}  →  «3 comisiones»
    """
    try:
        es_singular = int(cantidad) == 1
    except (TypeError, ValueError):
        es_singular = False
    if es_singular:
        return palabra
    if palabra in PLURALES:
        return PLURALES[palabra]
    return palabra + ("es" if palabra[-1] not in "aeiou" else "s")
