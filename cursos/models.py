from datetime import date

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class ConfiguracionSitio(models.Model):
    """Datos de contacto e institucionales que se muestran en la web pública.

    Es un singleton: siempre se trabaja con la fila de id=1.
    """

    nombre = models.CharField("nombre", max_length=120, default="CETACER")
    aniversario = models.CharField(
        "número de aniversario", max_length=10, blank=True, default="60",
        help_text="Se muestra en azul junto al nombre en el encabezado.",
    )
    descripcion_larga = models.CharField(
        "razón social", max_length=200,
        default="CÁMARA EMPRESARIA DEL TRANSPORTE AUTOMOTOR DE CARGAS DE ENTRE RÍOS",
    )
    cintillo = models.CharField(
        "texto del cintillo superior", max_length=120,
        default="TRANSPORTE · FORMACIÓN · ENTRE RÍOS",
    )
    titulo_hero = models.CharField("título principal", max_length=120, default="El próximo paso")
    titulo_hero_destacado = models.CharField(
        "continuación destacada del título", max_length=120, default="en tu camino."
    )
    bajada_hero = models.TextField(
        "bajada del título",
        default=(
            "Representamos a las empresas de transporte de cargas de la provincia. "
            "Gestioná la solicitud de turnos y consultá la grilla de fechas disponibles "
            "en un solo lugar."
        ),
    )
    whatsapp = models.CharField(
        "WhatsApp (formato internacional)", max_length=30, default="5493434695896",
        help_text="Sin signos ni espacios. Ej: 5493434695896",
    )
    whatsapp_visible = models.CharField(
        "WhatsApp como se muestra", max_length=40, default="343 469-5896"
    )
    telefonos = models.CharField(
        "teléfonos", max_length=200, default="(0343) 4330742 · 4332621 · 4332622"
    )
    telefono_principal = models.CharField(
        "teléfono del cintillo", max_length=40, default="(0343) 4330742"
    )
    email = models.EmailField("correo", default="administracion@cetacer.com")
    direccion = models.CharField(
        "dirección", max_length=200, default="Almirante Brown 2185, Paraná, Entre Ríos"
    )
    ciudad = models.CharField("ciudad", max_length=100, default="Paraná, Entre Ríos")
    facebook = models.URLField("Facebook", blank=True, default="https://facebook.com/cetacer")
    url_boleta = models.URLField(
        "URL de la boleta de pago", blank=True,
        default="https://sicapro.com.ar/solicitudonline.aspx",
    )
    inscripcion_online = models.BooleanField(
        "habilitar preinscripción online", default=True,
        help_text="Si está apagado, la web sólo ofrece el turno por WhatsApp.",
    )

    class Meta:
        verbose_name = "configuración del sitio"
        verbose_name_plural = "configuración del sitio"

    def __str__(self):
        return self.nombre

    @classmethod
    def vigente(cls):
        objeto, _ = cls.objects.get_or_create(pk=1)
        return objeto

    def enlace_whatsapp(self, texto):
        from urllib.parse import quote

        return f"https://wa.me/{self.whatsapp}?text={quote(texto)}"

    @property
    def whatsapp_general(self):
        return self.enlace_whatsapp(
            "Hola, quisiera solicitar un turno para un curso de CETACER."
        )

    @property
    def mapa_embed(self):
        from urllib.parse import quote

        return f"https://www.google.com/maps?q={quote(self.direccion)}&output=embed"


class Categoria(models.Model):
    """Agrupación de cursos, tal como se muestra en la web (Cargas Generales, etc.)."""

    nombre = models.CharField("nombre", max_length=120, unique=True)
    slug = models.SlugField("identificador en la URL", max_length=140, unique=True, blank=True)
    resumen = models.TextField("resumen", blank=True, help_text="Bajada que aparece bajo el título.")
    orden = models.PositiveIntegerField("orden", default=0, help_text="Menor número, aparece antes.")
    activa = models.BooleanField("visible en la web", default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)[:140]
        super().save(*args, **kwargs)

    @property
    def cursos_publicados(self):
        return self.cursos.filter(activo=True)

    @property
    def conteo_texto(self):
        total = self.cursos_publicados.count()
        return "1 curso" if total == 1 else f"{total} cursos"


class Curso(models.Model):
    """Un curso del catálogo. Las fechas concretas viven en Comision."""

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="cursos", verbose_name="categoría"
    )
    nombre = models.CharField("nombre", max_length=200)
    slug = models.SlugField("identificador en la URL", max_length=220, unique=True, blank=True)
    precio = models.DecimalField(
        "precio", max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Dejar vacío si el precio se informa por WhatsApp.",
    )
    precio_a_consultar = models.BooleanField(
        "mostrar «Consultar» en lugar del precio", default=False
    )
    duracion_horario = models.CharField(
        "duración y horario", max_length=200, default="A confirmar al asignar turno"
    )
    cupo_sugerido = models.PositiveIntegerField(
        "cupo sugerido", default=25,
        help_text="Cupo que se propone al crear una comisión nueva.",
    )
    cupo_texto = models.CharField(
        "texto del cupo en la web", max_length=100, default="Cupo limitado",
        help_text="Se usa si el curso no tiene comisiones publicadas.",
    )
    requisitos = models.TextField("requisitos", blank=True)
    descripcion = models.TextField("descripción ampliada", blank=True)
    link_externo = models.URLField("enlace a más información", blank=True)
    activo = models.BooleanField("visible en la web", default=True)
    orden = models.PositiveIntegerField("orden dentro de la categoría", default=0)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "curso"
        verbose_name_plural = "cursos"
        ordering = ["categoria__orden", "orden", "nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre)[:200] or "curso"
            slug = base
            contador = 2
            while Curso.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{contador}"
                contador += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("web:curso", kwargs={"slug": self.slug})

    @property
    def precio_texto(self):
        if self.precio_a_consultar or self.precio is None:
            return "Consultar"
        return f"${self.precio:,.0f}".replace(",", ".")

    def comisiones_publicadas(self):
        """Comisiones futuras y visibles, ordenadas por fecha."""
        return self.comisiones.filter(
            estado__in=[Comision.Estado.PUBLICADA, Comision.Estado.EN_CURSO],
            fecha_inicio__gte=date.today(),
        ).order_by("fecha_inicio")

    @property
    def tiene_fechas(self):
        return self.comisiones_publicadas().exists()

    @property
    def whatsapp_url(self):
        """Enlace de WhatsApp con el nombre del curso ya escrito en el mensaje."""
        return ConfiguracionSitio.vigente().enlace_whatsapp(
            f"Hola, quisiera pedir turno para: {self.nombre}"
        )


class Comision(models.Model):
    """Un dictado concreto del curso, con su fecha, cupo e inscriptos."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADA = "publicada", "Publicada"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    curso = models.ForeignKey(
        Curso, on_delete=models.CASCADE, related_name="comisiones", verbose_name="curso"
    )
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_fin = models.DateField(
        "fecha de finalización", null=True, blank=True,
        help_text="Sólo si el curso dura más de un día.",
    )
    hora_inicio = models.TimeField("hora de inicio", null=True, blank=True)
    hora_fin = models.TimeField("hora de finalización", null=True, blank=True)
    cupo = models.PositiveIntegerField("cupo", default=25)
    lugar = models.CharField(
        "lugar", max_length=200, blank=True,
        help_text="Si se deja vacío se usa la sede de la configuración del sitio.",
    )
    instructor = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="comisiones_a_cargo", verbose_name="instructor a cargo",
    )
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.BORRADOR
    )
    observaciones = models.TextField("observaciones internas", blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "comisión"
        verbose_name_plural = "comisiones"
        ordering = ["fecha_inicio", "hora_inicio"]
        indexes = [models.Index(fields=["fecha_inicio", "estado"])]

    def __str__(self):
        return f"{self.curso.nombre} — {self.fecha_texto}"

    def get_absolute_url(self):
        return reverse("panel:comision_detalle", kwargs={"pk": self.pk})

    @property
    def fecha_texto(self):
        from django.utils.formats import date_format

        inicio = date_format(self.fecha_inicio, "j \\d\\e F", use_l10n=True)
        if self.fecha_fin and self.fecha_fin != self.fecha_inicio:
            fin = date_format(self.fecha_fin, "j \\d\\e F", use_l10n=True)
            return f"{inicio} al {fin}"
        return inicio

    @property
    def horario_texto(self):
        if self.hora_inicio and self.hora_fin:
            return f"{self.hora_inicio:%H:%M} a {self.hora_fin:%H:%M} h"
        if self.hora_inicio:
            return f"Desde las {self.hora_inicio:%H:%M} h"
        return self.curso.duracion_horario

    @property
    def lugar_texto(self):
        return self.lugar or ConfiguracionSitio.vigente().direccion

    @property
    def inscriptos(self):
        """Inscripciones que ocupan cupo (todo menos las canceladas)."""
        return self.inscripciones.exclude(estado="cancelada")

    @property
    def cantidad_inscriptos(self):
        return self.inscriptos.count()

    @property
    def lugares_disponibles(self):
        return max(self.cupo - self.cantidad_inscriptos, 0)

    @property
    def completa(self):
        return self.cantidad_inscriptos >= self.cupo

    @property
    def ocupacion_porcentaje(self):
        if not self.cupo:
            return 0
        return min(round(self.cantidad_inscriptos * 100 / self.cupo), 100)

    @property
    def semaforo(self):
        """Color de referencia para el panel según la ocupación."""
        porcentaje = self.ocupacion_porcentaje
        if porcentaje >= 100:
            return "completa"
        if porcentaje >= 75:
            return "casi"
        if porcentaje >= 35:
            return "en-marcha"
        return "baja"

    @property
    def dias_faltantes(self):
        return (self.fecha_inicio - date.today()).days

    @property
    def es_futura(self):
        return self.fecha_inicio >= date.today()

    @property
    def visible_en_web(self):
        return self.estado in {self.Estado.PUBLICADA, self.Estado.EN_CURSO}
