# Migración del contenido del dominio viejo — Plan de implementación

> **Para quien ejecute esto:** SUB-SKILL REQUERIDA: usá
> `superpowers:subagent-driven-development` (recomendada) o
> `superpowers:executing-plans` para implementar tarea por tarea. Los pasos usan
> casillas (`- [ ]`) para seguimiento.

**Objetivo:** que ningún enlace de la web apunte a `cetacer.com`, moviendo ese
contenido a páginas editables desde el panel.

**Arquitectura:** app nueva `contenido` con `Pagina` y `EnlacePagina`, servida en
`/info/<slug>/` y administrada desde el panel con un formset inline. Los cursos
pierden `link_externo`; las formas de pago, que son iguales para todos, pasan a
`ConfiguracionSitio`.

**Stack:** Django 5.2, SQLite en desarrollo, `unittest` de Django (`manage.py test`).
Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-09-15-migracion-contenido-dominio-viejo-design.md`

## Restricciones globales

- Todo el código, los nombres de campo, los `verbose_name` y los mensajes al
  usuario van **en español**, siguiendo el estilo del repo.
- Los formularios del panel heredan de `panel.forms.BaseForm`, que aplica las
  clases CSS. No instanciar `forms.ModelForm` directo.
- Las vistas del panel se protegen con los decoradores de `panel/accesos.py`.
  Para páginas: `GESTION_CATALOGO` (Administración y arriba).
- Correr `python manage.py test` antes de cada commit. Las 51 pruebas existentes
  tienen que seguir pasando.
- El entorno es `.venv/`: usar `.venv/bin/python manage.py …`.
- Los slugs de las dos páginas migradas son exactamente `legislacion` e
  `informacion-util`.

---

### Task 1: App `contenido` con sus dos modelos

**Archivos:**
- Crear: `contenido/__init__.py`, `contenido/apps.py`, `contenido/models.py`, `contenido/migrations/__init__.py`
- Crear: `contenido/tests.py`
- Modificar: `config/settings.py` (INSTALLED_APPS)

**Interfaces:**
- Produce: `contenido.models.Pagina` (campos `titulo`, `slug`, `bajada`, `orden`,
  `publicada`, `actualizado`; método de clase `publicadas()`; `get_absolute_url()`)
  y `contenido.models.EnlacePagina` (campos `pagina`, `titulo`, `descripcion`,
  `grupo`, `url`, `archivo`, `orden`, `activo`; propiedades `destino` y
  `es_documento`).

- [ ] **Paso 1: Crear el esqueleto de la app**

```bash
cd /home/augusto/Documentos/CODIGOS/cetacer
.venv/bin/python manage.py startapp contenido
rm contenido/views.py contenido/admin.py
```

Dejá `contenido/apps.py` así:

```python
from django.apps import AppConfig


class ContenidoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contenido"
    verbose_name = "contenido institucional"
```

Y agregá `"contenido",` en `INSTALLED_APPS` de `config/settings.py`, después de
`"cursos",`.

- [ ] **Paso 2: Escribir las pruebas que fallan**

En `contenido/tests.py`:

```python
"""Pruebas de las páginas de contenido institucional."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from contenido.models import EnlacePagina, Pagina


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
```

- [ ] **Paso 3: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: FAIL con `ModuleNotFoundError` o `ImportError` sobre `contenido.models`.

- [ ] **Paso 4: Escribir los modelos**

En `contenido/models.py`:

```python
"""Páginas de contenido institucional, editables desde el panel.

Reemplazan a las páginas que vivían en el dominio viejo: un título, una bajada
y una lista de enlaces que pueden ser externos o documentos propios.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Pagina(models.Model):
    """Una página de contenido con su lista de enlaces."""

    titulo = models.CharField("título", max_length=120)
    slug = models.SlugField(
        "identificador en la URL", max_length=140, unique=True, blank=True
    )
    bajada = models.TextField(
        "bajada", blank=True, help_text="Texto que aparece bajo el título."
    )
    orden = models.PositiveIntegerField(
        "orden", default=0, help_text="Menor número, aparece antes."
    )
    publicada = models.BooleanField("visible en la web", default=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "página"
        verbose_name_plural = "páginas"
        ordering = ["orden", "titulo"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.titulo)[:140] or "pagina"
            slug = base
            contador = 2
            while Pagina.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{contador}"
                contador += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("web:pagina", kwargs={"slug": self.slug})

    @classmethod
    def publicadas(cls):
        return cls.objects.filter(publicada=True)


class EnlacePagina(models.Model):
    """Un destino dentro de una página: enlace externo o documento propio.

    Los enlaces a terceros se pudren —FADEEAC dio de baja varios de los que
    tenía el sitio viejo—, así que lo importante se sube como documento.
    """

    pagina = models.ForeignKey(
        Pagina, on_delete=models.CASCADE, related_name="enlaces", verbose_name="página"
    )
    titulo = models.CharField("título", max_length=200)
    descripcion = models.CharField("descripción", max_length=300, blank=True)
    grupo = models.CharField(
        "grupo", max_length=120, blank=True,
        help_text="Encabezado opcional. Los enlaces que comparten grupo se muestran juntos.",
    )
    url = models.URLField("enlace externo", blank=True)
    archivo = models.FileField("documento", upload_to="documentos/", blank=True)
    orden = models.PositiveIntegerField("orden", default=0)
    activo = models.BooleanField("visible", default=True)

    class Meta:
        verbose_name = "enlace"
        verbose_name_plural = "enlaces"
        ordering = ["orden", "id"]

    def __str__(self):
        return self.titulo

    def clean(self):
        if bool(self.url) == bool(self.archivo):
            raise ValidationError(
                "Cargá un enlace externo o subí un documento: uno de los dos, no los dos."
            )

    @property
    def destino(self):
        """A dónde lleva el enlace, sin que la plantilla tenga que decidir."""
        return self.archivo.url if self.archivo else self.url

    @property
    def es_documento(self):
        return bool(self.archivo)
```

- [ ] **Paso 5: Generar y aplicar la migración**

```bash
.venv/bin/python manage.py makemigrations contenido
.venv/bin/python manage.py migrate
```

- [ ] **Paso 6: Correr las pruebas**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: PASS, 9 pruebas.

`get_absolute_url()` todavía no se puede probar acá porque la ruta `web:pagina`
se crea en la Task 3. Su prueba va en esa tarea.

- [ ] **Paso 7: Correr la suite completa**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS, las 51 anteriores más las nuevas.

- [ ] **Paso 8: Commit**

```bash
git add contenido/ config/settings.py
git commit -m "Modelos de páginas de contenido institucional"
```

---

### Task 2: Agrupación de enlaces

**Archivos:**
- Modificar: `contenido/models.py` (método `Pagina.enlaces_agrupados`)
- Modificar: `contenido/tests.py`

**Interfaces:**
- Consume: `Pagina` y `EnlacePagina` de la Task 1.
- Produce: `Pagina.enlaces_agrupados()` → `list[tuple[str, list[EnlacePagina]]]`.
  El primer elemento de cada tupla es el nombre del grupo (`""` para los
  sueltos). Lo consume la plantilla de la Task 3.

- [ ] **Paso 1: Escribir las pruebas que fallan**

Agregá a `contenido/tests.py`:

```python
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
```

- [ ] **Paso 2: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test contenido.tests.EnlacesAgrupadosTests -v 2`
Esperado: FAIL con `AttributeError: 'Pagina' object has no attribute 'enlaces_agrupados'`.

- [ ] **Paso 3: Implementar el método**

Agregá a `Pagina` en `contenido/models.py`, después de `publicadas()`:

```python
    def enlaces_agrupados(self):
        """Los enlaces visibles como [(grupo, [enlaces…])].

        Los que no tienen grupo van primero, sueltos. El resto conserva el orden
        en que aparece el primer enlace de cada grupo, para que el orden de la
        página se maneje desde un solo lugar: el campo `orden` de cada enlace.
        """
        grupos = {}
        for enlace in self.enlaces.filter(activo=True):
            grupos.setdefault(enlace.grupo, []).append(enlace)
        sueltos = grupos.pop("", None)
        resultado = [("", sueltos)] if sueltos else []
        resultado.extend(grupos.items())
        return resultado
```

- [ ] **Paso 4: Correr las pruebas**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: PASS.

- [ ] **Paso 5: Commit**

```bash
git add contenido/
git commit -m "Agrupar los enlaces de una página por su campo grupo"
```

---

### Task 3: Página pública en `/info/<slug>/`

**Archivos:**
- Modificar: `web/urls.py`, `web/views.py`, `web/context_processors.py`
- Crear: `templates/web/pagina.html`
- Crear: `web/templatetags/__init__.py`, `web/templatetags/web_extras.py`
- Modificar: `config/settings.py` (registrar el context processor nuevo)
- Modificar: `contenido/tests.py`

**Interfaces:**
- Consume: `Pagina.publicadas()` y `Pagina.enlaces_agrupados()` de las Tasks 1 y 2.
- Produce: la ruta `web:pagina` (kwarg `slug`), la variable de contexto global
  `paginas` (dict `{slug: Pagina}`) y el filtro `buscar_pagina`, que consume la
  Task 4.

**Ojo con el guión.** El slug `informacion-util` **no** se puede buscar con
`{{ paginas.informacion-util }}`: el guión no es válido en una búsqueda de
variable de Django y la plantilla renderiza vacío sin avisar. Por eso existe el
filtro `buscar_pagina`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

Agregá a `contenido/tests.py`:

```python
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
```

- [ ] **Paso 2: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test contenido.tests.PaginaPublicaTests -v 2`
Esperado: FAIL con 404 en `/info/legislacion/`.

- [ ] **Paso 3: Agregar la ruta**

En `web/urls.py`, antes de la ruta de cursos:

```python
    path("info/<slug:slug>/", views.pagina, name="pagina"),
```

- [ ] **Paso 4: Agregar la vista**

En `web/views.py`, importá el modelo arriba:

```python
from contenido.models import Pagina
```

y agregá la vista después de `catalogo`:

```python
def pagina(request, slug):
    """Una página de contenido institucional, con sus enlaces agrupados."""
    pagina = get_object_or_404(Pagina.publicadas(), slug=slug)
    return render(request, "web/pagina.html", {
        "pagina": pagina,
        "grupos": pagina.enlaces_agrupados(),
    })
```

- [ ] **Paso 5: Agregar el context processor**

En `web/context_processors.py`, al final:

```python
def paginas_de_contenido(request):
    """Las páginas publicadas, para que cualquier plantilla pueda enlazarlas.

    Va aparte de `configuracion_sitio` para que un error en una no deje sin
    contexto a la otra.
    """
    from contenido.models import Pagina

    try:
        return {"paginas": {p.slug: p for p in Pagina.publicadas()}}
    except Exception:
        # Durante las migraciones iniciales la tabla todavía no existe.
        return {"paginas": {}}
```

Y registralo en `config/settings.py`, después de
`"web.context_processors.configuracion_sitio",`:

```python
                "web.context_processors.paginas_de_contenido",
```

- [ ] **Paso 6: Agregar el filtro de plantilla**

Creá `web/templatetags/__init__.py` vacío y `web/templatetags/web_extras.py`:

```python
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
```

- [ ] **Paso 7: Crear la plantilla**

`templates/web/pagina.html`:

```html
{% extends "web/base.html" %}
{% block title %}{{ pagina.titulo }} — {{ sitio.nombre }}{% endblock %}
{% block description %}{{ pagina.bajada }}{% endblock %}

{% block contenido %}
<section class="contenedor seccion-blanca">
  <p class="migas">
    <a href="{% url 'web:inicio' %}">Inicio</a> › {{ pagina.titulo }}
  </p>

  <h1 style="margin-top:20px">{{ pagina.titulo }}</h1>
  {% if pagina.bajada %}
    <p style="max-width:70ch">{{ pagina.bajada|linebreaksbr }}</p>
  {% endif %}

  {% for grupo, enlaces in grupos %}
    <div class="ficha__bloque">
      {% if grupo %}<h2>{{ grupo }}</h2>{% endif %}
      <ul style="list-style:none;padding:0;margin:0">
        {% for enlace in enlaces %}
          <li style="padding:10px 0;border-bottom:1px solid var(--borde)">
            <a href="{{ enlace.destino }}" rel="noopener"
               {% if not enlace.es_documento %}target="_blank"{% endif %}>
              {{ enlace.titulo }}{% if enlace.es_documento %} (PDF){% endif %} →
            </a>
            {% if enlace.descripcion %}
              <div style="font-size:14.5px;color:var(--etiqueta);margin-top:2px">
                {{ enlace.descripcion }}
              </div>
            {% endif %}
          </li>
        {% endfor %}
      </ul>
    </div>
  {% empty %}
    <p style="color:var(--etiqueta)">Todavía no hay enlaces cargados en esta página.</p>
  {% endfor %}
</section>
{% endblock %}
```

- [ ] **Paso 8: Correr las pruebas**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: PASS.

- [ ] **Paso 9: Correr la suite completa**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS.

- [ ] **Paso 10: Commit**

```bash
git add web/ templates/web/pagina.html config/settings.py contenido/tests.py
git commit -m "Servir las páginas de contenido en /info/<slug>/"
```

---

### Task 4: Las tarjetas del inicio dejan de salir del sitio

**Archivos:**
- Modificar: `templates/web/inicio.html:56-66`
- Modificar: `contenido/tests.py`

**Interfaces:**
- Consume: la variable de contexto `paginas` y el filtro `buscar_pagina` de la Task 3.

Esta tarea es la que cierra el bug original: después de ella, ninguna plantilla
enlaza al dominio viejo.

- [ ] **Paso 1: Escribir la prueba de regresión**

Agregá a `contenido/tests.py`, con estos imports arriba del archivo:

```python
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
```

```python
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
```

Y la prueba de que las tarjetas siguen funcionando:

```python
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
```

- [ ] **Paso 2: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test contenido.tests.SinEnlacesAlDominioViejoTests contenido.tests.TarjetasDelInicioTests -v 2`
Esperado: FAIL. La de regresión lista `web/inicio.html`; las de las tarjetas
fallan porque todavía enlazan afuera.

- [ ] **Paso 3: Cargar el filtro en la plantilla**

En la primera línea de `templates/web/inicio.html`, después del `{% extends %}`:

```html
{% load web_extras %}
```

- [ ] **Paso 4: Reemplazar las dos tarjetas**

En `templates/web/inicio.html`, cambiá el bloque de Legislación:

```html
    <div>
      <h3>Legislación</h3>
      <p>Normativa vigente del transporte automotor de cargas.</p>
      {% with p=paginas|buscar_pagina:"legislacion" %}
        {% if p %}<a href="{{ p.get_absolute_url }}">Ver legislación →</a>{% endif %}
      {% endwith %}
    </div>
```

y el de Información útil:

```html
    <div>
      <h3>Información útil</h3>
      <p>Trámites y documentación para asociados y conductores.</p>
      {% with p=paginas|buscar_pagina:"informacion-util" %}
        {% if p %}<a href="{{ p.get_absolute_url }}">Ver información útil →</a>{% endif %}
      {% endwith %}
    </div>
```

No toques la tarjeta de FADEEAC: apunta a un dominio de tercero que sigue vivo.

- [ ] **Paso 5: Correr las pruebas**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: PASS.

- [ ] **Paso 6: Correr la suite completa**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS.

- [ ] **Paso 7: Commit**

```bash
git add templates/web/inicio.html contenido/tests.py
git commit -m "Las tarjetas del inicio apuntan a las páginas internas"
```

---

### Task 5: Administrar las páginas desde el panel

**Archivos:**
- Modificar: `panel/forms.py`, `panel/views.py`, `panel/urls.py`
- Crear: `templates/panel/paginas.html`, `templates/panel/pagina_form.html`
- Modificar: `templates/panel/base.html:52-58` (menú)
- Modificar: `cuentas/permisos.py`
- Modificar: `contenido/tests.py`

**Interfaces:**
- Consume: `Pagina` y `EnlacePagina` de la Task 1.
- Produce: las rutas `panel:paginas`, `panel:pagina_nueva`, `panel:pagina_editar`
  y `panel:pagina_eliminar`; el formset `panel.forms.EnlaceFormSet`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

Agregá a `contenido/tests.py`:

```python
from cuentas.models import Rol, Usuario


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
```

- [ ] **Paso 2: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test contenido.tests.PanelPaginasTests -v 2`
Esperado: FAIL con 404 en `/panel/paginas/`.

- [ ] **Paso 3: Agregar los formularios**

En `panel/forms.py`, importá arriba:

```python
from django.forms import inlineformset_factory

from contenido.models import EnlacePagina, Pagina
```

y agregá al final:

```python
class PaginaForm(BaseForm):
    class Meta:
        model = Pagina
        fields = ["titulo", "bajada", "orden", "publicada"]


class EnlacePaginaForm(BaseForm):
    class Meta:
        model = EnlacePagina
        fields = ["titulo", "descripcion", "grupo", "url", "archivo", "orden", "activo"]
        help_texts = {
            "grupo": "Dejalo vacío si el enlace va suelto arriba de todo.",
        }


#: Los enlaces se cargan en la misma pantalla que la página.
EnlaceFormSet = inlineformset_factory(
    Pagina, EnlacePagina, form=EnlacePaginaForm, extra=3, can_delete=True
)
```

- [ ] **Paso 4: Agregar las vistas**

En `panel/views.py`, sumá a los imports:

```python
from contenido.models import Pagina
```

y en el import de `.forms`, agregá `EnlaceFormSet` y `PaginaForm`.

Agregá las vistas después de `categoria_editar`:

```python
@GESTION_CATALOGO
def paginas_lista(request):
    return render(request, "panel/paginas.html", {
        "seccion": "paginas",
        "paginas_cargadas": Pagina.objects.prefetch_related("enlaces"),
    })


@GESTION_CATALOGO
def pagina_editar(request, pk=None):
    """La página y sus enlaces se guardan juntos o no se guarda nada."""
    pagina = get_object_or_404(Pagina, pk=pk) if pk else None
    if request.method == "POST":
        formulario = PaginaForm(request.POST, instance=pagina)
        enlaces = EnlaceFormSet(request.POST, request.FILES, instance=pagina)
        if formulario.is_valid() and enlaces.is_valid():
            with transaction.atomic():
                guardada = formulario.save()
                enlaces.instance = guardada
                enlaces.save()
            messages.success(request, f"Página «{guardada.titulo}» guardada.")
            return redirect("panel:paginas")
        messages.error(request, "Revisá los campos marcados en rojo.")
    else:
        formulario = PaginaForm(instance=pagina)
        enlaces = EnlaceFormSet(instance=pagina)
    return render(request, "panel/pagina_form.html", {
        "seccion": "paginas",
        "form": formulario,
        "enlaces": enlaces,
        "pagina": pagina,
    })


@GESTION_CATALOGO
def pagina_eliminar(request, pk):
    pagina = get_object_or_404(Pagina, pk=pk)
    titulo = pagina.titulo
    pagina.delete()
    messages.success(request, f"Página «{titulo}» eliminada.")
    return redirect("panel:paginas")
```

**Importante:** el contexto usa `paginas_cargadas`, no `paginas`, porque el
context processor de la Task 3 ya ocupa ese nombre en todas las plantillas.

- [ ] **Paso 5: Agregar las rutas**

En `panel/urls.py`, en el bloque «Catálogo», después de las categorías:

```python
    path("paginas/", views.paginas_lista, name="paginas"),
    path("paginas/nueva/", views.pagina_editar, name="pagina_nueva"),
    path("paginas/<int:pk>/", views.pagina_editar, name="pagina_editar"),
    path("paginas/<int:pk>/eliminar/", views.pagina_eliminar, name="pagina_eliminar"),
```

- [ ] **Paso 6: Crear el listado**

`templates/panel/paginas.html`:

```html
{% extends "panel/base.html" %}
{% block title %}Páginas{% endblock %}
{% block encabezado %}Páginas de contenido{% endblock %}
{% block bajada %}
  <div class="bajada">Legislación, información útil y cualquier otra página de enlaces que quieras publicar.</div>
{% endblock %}
{% block acciones %}
  <a class="boton boton--primario" href="{% url 'panel:pagina_nueva' %}">+ Nueva página</a>
{% endblock %}

{% block contenido %}
<div class="tarjeta">
  <table class="tabla">
    <thead>
      <tr><th>Página</th><th>Enlaces</th><th>Estado</th><th></th></tr>
    </thead>
    <tbody>
      {% for p in paginas_cargadas %}
        <tr>
          <td>
            <strong>{{ p.titulo }}</strong>
            <div style="font-size:13.5px;color:var(--etiqueta)">/info/{{ p.slug }}/</div>
          </td>
          <td>{{ p.enlaces.count }}</td>
          <td>{% if p.publicada %}Publicada{% else %}Borrador{% endif %}</td>
          <td><a href="{% url 'panel:pagina_editar' p.pk %}">Editar</a></td>
        </tr>
      {% empty %}
        <tr><td colspan="4">Todavía no hay páginas cargadas.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

La clase `tabla` ya existe en `static/css/panel.css`; el resto va con estilo
inline, como hacen las otras plantillas del panel.

- [ ] **Paso 7: Crear el formulario**

`templates/panel/pagina_form.html`:

```html
{% extends "panel/base.html" %}
{% block title %}{% if pagina %}Editar página{% else %}Nueva página{% endif %}{% endblock %}
{% block encabezado %}{% if pagina %}{{ pagina.titulo }}{% else %}Nueva página{% endif %}{% endblock %}
{% block bajada %}
  <div class="bajada">Todo lo que se cargue acá se ve en la web apenas guardás.</div>
{% endblock %}

{% block contenido %}
<form class="tarjeta formulario" method="post" enctype="multipart/form-data">
  {% csrf_token %}

  <div class="seccion-form">
    <div class="seccion-form__titulo">1. La página</div>
    <p class="seccion-form__ayuda">El título arma la dirección web. Si la despublicás, deja de verse y las tarjetas del inicio dejan de enlazarla.</p>
    {% include "panel/_campo.html" with campo=form.titulo %}
    {% include "panel/_campo.html" with campo=form.bajada %}
    <div class="grilla-campos">
      {% include "panel/_campo.html" with campo=form.orden %}
      {% include "panel/_campo.html" with campo=form.publicada %}
    </div>
  </div>

  <div class="seccion-form">
    <div class="seccion-form__titulo">2. Enlaces</div>
    <p class="seccion-form__ayuda">
      Cada fila es un enlace externo <em>o</em> un documento subido, nunca las dos cosas.
      Si el enlace importa de verdad, subí el archivo: los sitios ajenos dan de baja sus PDF sin avisar.
      Poné el mismo texto en «grupo» para que aparezcan juntos bajo ese encabezado.
    </p>
    {{ enlaces.management_form }}
    {% for formulario_enlace in enlaces %}
      <div class="seccion-form" style="border:1px solid var(--borde);padding:14px;margin-bottom:12px">
        {{ formulario_enlace.id }}
        <div class="grilla-campos">
          {% include "panel/_campo.html" with campo=formulario_enlace.titulo %}
          {% include "panel/_campo.html" with campo=formulario_enlace.grupo %}
        </div>
        {% include "panel/_campo.html" with campo=formulario_enlace.descripcion %}
        <div class="grilla-campos">
          {% include "panel/_campo.html" with campo=formulario_enlace.url %}
          {% include "panel/_campo.html" with campo=formulario_enlace.archivo %}
        </div>
        <div class="grilla-campos">
          {% include "panel/_campo.html" with campo=formulario_enlace.orden %}
          {% include "panel/_campo.html" with campo=formulario_enlace.activo %}
          {% if formulario_enlace.instance.pk %}
            {% include "panel/_campo.html" with campo=formulario_enlace.DELETE %}
          {% endif %}
        </div>
        {% for error in formulario_enlace.non_field_errors %}
          <div class="error">{{ error }}</div>
        {% endfor %}
      </div>
    {% endfor %}
  </div>

  <div class="acciones-form">
    <button class="boton boton--primario" type="submit">Guardar página</button>
    <a class="boton boton--secundario" href="{% url 'panel:paginas' %}">Cancelar</a>
    {% if pagina %}
      <a class="boton boton--secundario derecha" href="{{ pagina.get_absolute_url }}" target="_blank">Ver en la web →</a>
    {% endif %}
  </div>
</form>

{% if pagina %}
  <form class="tarjeta formulario" method="post" action="{% url 'panel:pagina_eliminar' pagina.pk %}"
        style="margin-top:18px;border-color:#fda29b"
        onsubmit="return confirm('¿Eliminar «{{ pagina.titulo|escapejs }}» y todos sus enlaces?')">
    {% csrf_token %}
    <div class="tarjeta__titulo" style="color:var(--rojo)">Eliminar página</div>
    <p class="tarjeta__ayuda">Se borran también sus enlaces. Si sólo querés sacarla de la web, despublicala arriba.</p>
    <button class="boton boton--peligro" type="submit">Eliminar esta página</button>
  </form>
{% endif %}
{% endblock %}
```

La clase `error` es la que usa `templates/panel/_campo.html` para los errores de
campo; acá sirve para los de formulario, que es donde cae el `clean()` del
modelo.

- [ ] **Paso 8: Agregar la entrada al menú**

En `templates/panel/base.html`, agregá la entrada justo después del enlace a
Cursos (línea 37). Va **fuera** del bloque
`{% if user.is_superuser or rol_actual.value == "Dirección" %}`, porque la
sección es de Administración para arriba, no sólo de Dirección:

```html
      <a href="{% url 'panel:paginas' %}" class="{% if seccion == 'paginas' %}activo{% endif %}">
        {% include "panel/iconos.html" with icono="engranaje" %} Páginas
      </a>
```

Si `iconos.html` tiene un ícono más adecuado que `engranaje`, usalo; mirá la
lista con `grep -o 'icono == "[a-z]*"' templates/panel/iconos.html`.

- [ ] **Paso 9: Sumar los permisos**

En `cuentas/permisos.py`, agregá a la `MATRIZ`:

- En `Rol.DIRECCION` y `Rol.ADMINISTRACION`:

```python
        "contenido.pagina": TODOS,
        "contenido.enlacepagina": TODOS,
```

- En `Rol.COORDINACION` y `Rol.RECEPCION`:

```python
        "contenido.pagina": LECTURA,
        "contenido.enlacepagina": LECTURA,
```

`Rol.INSTRUCTOR` no lleva nada.

- [ ] **Paso 10: Sincronizar los grupos**

Corré: `.venv/bin/python manage.py init_roles`
Esperado: los cinco grupos actualizados, sin error.

- [ ] **Paso 11: Correr las pruebas**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: PASS.

- [ ] **Paso 12: Correr la suite completa**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS.

- [ ] **Paso 13: Commit**

```bash
git add panel/ templates/panel/ cuentas/permisos.py contenido/tests.py
git commit -m "Administrar las páginas de contenido desde el panel"
```

---

### Task 6: Sacar `link_externo` y sumar las formas de pago

**Archivos:**
- Modificar: `cursos/models.py` (quitar `Curso.link_externo`, sumar 4 campos a `ConfiguracionSitio`)
- Modificar: `panel/forms.py:47`, `templates/panel/curso_form.html:52`
- Modificar: `templates/panel/configuracion.html`
- Modificar: `templates/web/curso.html:107-111`
- Modificar: `cursos/management/commands/cargar_datos.py` (quitar las 6 claves `"link"`)
- Modificar: `cursos/tests.py`

**Interfaces:**
- Produce: `ConfiguracionSitio.pago_alias`, `.pago_banco`, `.pago_titular` y
  `.pago_aclaracion`.
- Rompe: `Curso.link_externo` deja de existir. Nada más lo usa después de la Task 4.

- [ ] **Paso 1: Escribir las pruebas que fallan**

Agregá a `cursos/tests.py`:

```python
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
        sitio.pago_aclaracion = ""
        sitio.save()
        respuesta = self.client.get(self.curso.get_absolute_url())
        self.assertNotContains(respuesta, "FORMAS DE PAGO")

    def test_el_curso_ya_no_tiene_link_externo(self):
        self.assertFalse(hasattr(self.curso, "link_externo"))
```

- [ ] **Paso 2: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test cursos.tests.FormasDePagoTests -v 2`
Esperado: FAIL con `AttributeError` sobre `pago_alias`.

- [ ] **Paso 3: Cambiar el modelo**

En `cursos/models.py`, borrá la línea de `Curso`:

```python
    link_externo = models.URLField("enlace a más información", blank=True)
```

y agregá a `ConfiguracionSitio`, después de `url_boleta`:

```python
    pago_alias = models.CharField(
        "alias para transferencias", max_length=60, blank=True,
        default="FPT.LICENCIAPROF",
    )
    pago_banco = models.CharField(
        "banco", max_length=80, blank=True, default="Banco Nación"
    )
    pago_titular = models.CharField("titular de la cuenta", max_length=120, blank=True)
    pago_aclaracion = models.TextField(
        "aclaración sobre el pago", blank=True,
        default=(
            "Enviá el comprobante por WhatsApp junto con la foto del DNI y de la "
            "licencia de conducir, frente y dorso."
        ),
    )
```

- [ ] **Paso 4: Sacar el campo del panel**

En `panel/forms.py`, quitá `"link_externo",` de la lista `fields` de `CursoForm`
(línea 47). En `templates/panel/curso_form.html`, borrá la línea 52:

```html
    {% include "panel/_campo.html" with campo=form.link_externo %}
```

En `templates/panel/configuracion.html`, agregá una sección nueva antes de la de
visibilidad:

```html
  <div class="seccion-form">
    <div class="seccion-form__titulo">Formas de pago</div>
    <p class="seccion-form__ayuda">
      Se muestran en la ficha de cada curso, debajo del precio. Son las mismas para
      todo el catálogo, por eso se cargan una sola vez acá.
    </p>
    <div class="grilla-campos">
      {% include "panel/_campo.html" with campo=form.pago_alias %}
      {% include "panel/_campo.html" with campo=form.pago_banco %}
    </div>
    {% include "panel/_campo.html" with campo=form.pago_titular %}
    {% include "panel/_campo.html" with campo=form.pago_aclaracion %}
  </div>
```

`ConfiguracionForm` usa `exclude = []`, así que toma los campos nuevos sola.

- [ ] **Paso 5: Cambiar la ficha del curso**

En `templates/web/curso.html`, reemplazá el bloque de `link_externo`
(líneas 107-111) por:

```html
      {% if sitio.pago_alias or sitio.pago_aclaracion %}
        <div style="height:1px;background:var(--borde);margin:22px 0"></div>
        <div class="etiqueta">FORMAS DE PAGO</div>
        {% if sitio.pago_alias %}
          <div class="dato-valor">
            Alias {{ sitio.pago_alias }}{% if sitio.pago_banco %} · {{ sitio.pago_banco }}{% endif %}
          </div>
        {% endif %}
        {% if sitio.pago_titular %}
          <div class="dato-valor">Titular: {{ sitio.pago_titular }}</div>
        {% endif %}
        {% if sitio.pago_aclaracion %}
          <p style="font-size:14px;color:var(--etiqueta);margin-top:6px">
            {{ sitio.pago_aclaracion|linebreaksbr }}
          </p>
        {% endif %}
      {% endif %}
```

El enlace a la boleta e-SICAPRO que viene abajo **no se toca**: `sicapro.com.ar`
es un dominio de tercero que sigue vivo.

- [ ] **Paso 6: Limpiar el comando de carga**

En `cursos/management/commands/cargar_datos.py` hay que tocar dos cosas:

1. Borrar las seis claves `"link": …` de la constante `CATALOGO`.
2. Borrar la línea 175, que es la que las usa:

```python
                        "link_externo": datos_curso["link"],
```

Verificá que no quedó nada:

```bash
grep -n '"link"\|link_externo' cursos/management/commands/cargar_datos.py
```

Esperado: sin resultados.

- [ ] **Paso 7: Generar y aplicar la migración**

```bash
.venv/bin/python manage.py makemigrations cursos
.venv/bin/python manage.py migrate
```

Esperado: una migración que borra `curso.link_externo` y agrega los cuatro
campos de pago.

- [ ] **Paso 8: Correr las pruebas**

Corré: `.venv/bin/python manage.py test cursos -v 2`
Esperado: PASS.

- [ ] **Paso 9: Correr la suite completa**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS. Si algo falla por `link_externo`, buscá los restos con
`grep -rn "link_externo" --include="*.py" --include="*.html" . | grep -v .venv`.

- [ ] **Paso 10: Commit**

```bash
git add cursos/ panel/forms.py templates/
git commit -m "Reemplazar el enlace externo del curso por las formas de pago"
```

---

### Task 7: Cargar las dos páginas con los enlaces ya curados

**Archivos:**
- Modificar: `cursos/management/commands/cargar_datos.py`
- Modificar: `contenido/tests.py`

**Interfaces:**
- Consume: `Pagina` y `EnlacePagina` de la Task 1.

Los enlaces son los del relevamiento del spec, ya depurados: **no** copies la
lista del sitio viejo, que tiene 9 enlaces muertos.

- [ ] **Paso 1: Escribir las pruebas que fallan**

Agregá a `contenido/tests.py`:

```python
from django.core.management import call_command


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
```

- [ ] **Paso 2: Correr las pruebas para confirmar que fallan**

Corré: `.venv/bin/python manage.py test contenido.tests.CargarPaginasTests -v 2`
Esperado: FAIL, las páginas no existen.

- [ ] **Paso 3: Agregar la definición de las páginas**

En `cursos/management/commands/cargar_datos.py`, después de la constante
`CATALOGO`:

```python
# Relevado del sitio viejo el 2026-09-15 y depurado: 9 de los 16 enlaces
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
                "descripcion": "Federación Argentina de Entidades Empresarias del Autotransporte de Cargas.",
                "url": "https://www.fadeeac.org.ar/",
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
        ],
    },
]
```

- [ ] **Paso 4: Cargarlas desde el comando**

En `cursos/management/commands/cargar_datos.py`, importá arriba:

```python
from pathlib import Path

from django.conf import settings

from contenido.models import EnlacePagina, Pagina
```

Agregá el método a la clase `Command`:

```python
    def _cargar_paginas(self):
        """Crea las páginas institucionales. Idempotente, como el resto."""
        for datos in PAGINAS:
            pagina, _ = Pagina.objects.update_or_create(
                slug=datos["slug"],
                defaults={
                    "titulo": datos["titulo"],
                    "bajada": datos["bajada"],
                    "orden": datos["orden"],
                    "publicada": True,
                },
            )
            for enlace in datos.get("enlaces", []):
                archivo = enlace.get("archivo", "")
                if archivo and not (Path(settings.MEDIA_ROOT) / archivo).exists():
                    # El PDF no está en esta instalación; se sube desde el panel.
                    continue
                EnlacePagina.objects.update_or_create(
                    pagina=pagina,
                    titulo=enlace["titulo"],
                    defaults={
                        "descripcion": enlace.get("descripcion", ""),
                        "grupo": enlace.get("grupo", ""),
                        "url": enlace.get("url", ""),
                        "archivo": archivo,
                        "orden": enlace.get("orden", 0),
                        "activo": True,
                    },
                )
```

y llamalo dentro de `handle`. Los mensajes hoy van de `1/4` (línea 152) a `4/4`
(línea 182): cambiá esos cuatro a `/5` y sumá el quinto después de los usuarios:

```python
        self.stdout.write("5/5  Páginas institucionales...")
        self._cargar_paginas()
```

- [ ] **Paso 5: Correr las pruebas**

Corré: `.venv/bin/python manage.py test contenido -v 2`
Esperado: PASS.

- [ ] **Paso 6: Probarlo contra la base de desarrollo**

```bash
.venv/bin/python manage.py cargar_datos --demo
.venv/bin/python manage.py runserver 8000 &
sleep 3
curl -s -o /dev/null -w "inicio: %{http_code}\n" http://127.0.0.1:8000/
curl -s -o /dev/null -w "legislacion: %{http_code}\n" http://127.0.0.1:8000/info/legislacion/
curl -s -o /dev/null -w "info util: %{http_code}\n" http://127.0.0.1:8000/info/informacion-util/
curl -s http://127.0.0.1:8000/ | grep -c "cetacer.com"
```

Esperado: tres veces 200, y `0` apariciones de `cetacer.com` en el HTML del
inicio. Frená el servidor al terminar.

- [ ] **Paso 7: Correr la suite completa**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS.

- [ ] **Paso 8: Commit**

```bash
git add cursos/management/commands/cargar_datos.py contenido/tests.py
git commit -m "Cargar Legislación e Información útil con los enlaces verificados"
```

---

### Task 8: Documentar y cerrar

**Archivos:**
- Modificar: `README.md`

- [ ] **Paso 1: Actualizar la estructura en el README**

En la sección «Estructura», agregá la línea:

```
contenido/       Páginas institucionales de enlaces, editables desde el panel
```

- [ ] **Paso 2: Documentar los documentos propios**

Agregá al README, después de «Exportaciones»:

```markdown
## Páginas de contenido

Legislación e Información útil son páginas cargadas desde el panel
(**Páginas**), no código. Cada una es un título, una bajada y una lista de
enlaces que pueden ser externos o documentos subidos.

Subí como documento todo lo que importe. Los enlaces a sitios ajenos se
pudren: de los 16 que tenía el sitio anterior, 9 ya estaban muertos cuando se
migró el contenido, incluidos dos PDF de FADEEAC.

Los archivos van a `media/documentos/`, que está fuera del control de versiones:
en una instalación nueva hay que volver a subirlos desde el panel.
```

- [ ] **Paso 3: Verificar que no quedó nada del dominio viejo**

```bash
grep -rn "cetacer\.com" --include="*.py" --include="*.html" . | grep -v .venv | grep -v "@cetacer.com"
```

Esperado: sin resultados. Los `@cetacer.com` que quedan son direcciones de
correo, no enlaces, y son correctas.

- [ ] **Paso 4: Correr la suite completa una última vez**

Corré: `.venv/bin/python manage.py test`
Esperado: PASS, sin fallas ni errores.

- [ ] **Paso 5: Commit**

```bash
git add README.md
git commit -m "Documentar las páginas de contenido"
```

---

## Qué queda pendiente de CETACER

Estos cuatro puntos no bloquean nada: se cargan desde el panel cuando lleguen
las respuestas.

1. Titular de la cuenta del alias `FPT.LICENCIAPROF` → `pago_titular`.
2. Decreto provincial 03307-07, hoy sin URL viva.
3. Confirmar que el texto consolidado de la Ley 24449 reemplaza a la Ley 26363.
4. Pedirle a FADEEAC el Checklist y «Qué debe saber un transportista», que dieron
   de baja.
