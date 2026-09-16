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
