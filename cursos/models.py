import re
from datetime import date

from django.core.validators import FileExtensionValidator
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
        "razón social", max_length=200, blank=True,
        help_text="Se muestra en la pantalla de ingreso del panel.",
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
    whatsapp_socios = models.CharField(
        "WhatsApp de socios", max_length=40, blank=True, default="(0343) 4503288",
        help_text="Con la característica. Ej: (0343) 4503288",
    )
    email = models.EmailField("correo", default="administracion@cetacer.com")
    direccion = models.CharField(
        "dirección", max_length=200, default="Almirante Brown 2185, Paraná, Entre Ríos"
    )
    ciudad = models.CharField("ciudad", max_length=100, default="Paraná, Entre Ríos")
    instagram = models.URLField("Instagram", blank=True)
    video_cursos = models.URLField(
        "video de la sección de cursos", blank=True,
        default="https://www.youtube.com/watch?v=0YY-WsyDzD8",
        help_text="Enlace de YouTube. Si se deja vacío, la sección va sin video.",
    )
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
    def whatsapp_socios_url(self):
        """wa.me del número de socios: sin el 0 de la característica y con el 54."""
        digitos = re.sub(r"\D", "", self.whatsapp_socios).lstrip("0")
        return f"https://wa.me/54{digitos}" if digitos else ""

    @property
    def video_cursos_embed(self):
        """URL para el iframe, o vacío si el enlace no es de YouTube."""
        from urllib.parse import parse_qs, urlparse

        url = urlparse(self.video_cursos)
        host = url.netloc.lower().removeprefix("www.").removeprefix("m.")
        video = ""
        if host == "youtu.be":
            video = url.path.strip("/")
        elif host in {"youtube.com", "youtube-nocookie.com"}:
            if url.path == "/watch":
                video = parse_qs(url.query).get("v", [""])[0]
            elif url.path.startswith(("/embed/", "/shorts/", "/live/")):
                video = url.path.split("/")[2]
        if not re.fullmatch(r"[\w-]{6,20}", video):
            return ""
        return f"https://www.youtube-nocookie.com/embed/{video}"

    @property
    def portada_visible(self):
        """Las imágenes de portada que se muestran, en orden."""
        return self.imagenes_portada.filter(activa=True)

    @property
    def mapa_embed(self):
        from urllib.parse import quote

        return f"https://www.google.com/maps?q={quote(self.direccion)}&output=embed"


class ImagenPortada(models.Model):
    """Fotos que rotan de fondo en la portada del inicio.

    Con una sola imagen la portada queda fija; con varias se van alternando.
    Si no hay ninguna cargada, la web cae en la foto del camión que viene con
    el proyecto, así la portada nunca queda vacía.
    """

    sitio = models.ForeignKey(
        ConfiguracionSitio, on_delete=models.CASCADE,
        related_name="imagenes_portada", verbose_name="sitio",
    )
    imagen = models.FileField(
        "imagen",
        upload_to="portada/",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
        help_text="Apaisada y de al menos 1600 px de ancho: se recorta a lo alto.",
    )
    descripcion = models.CharField(
        "de qué es la foto", max_length=120, blank=True,
        help_text="Para uso interno: ayuda a distinguirlas en esta lista.",
    )
    orden = models.PositiveIntegerField("orden", default=0)
    activa = models.BooleanField("visible en la web", default=True)

    class Meta:
        verbose_name = "imagen de portada"
        verbose_name_plural = "imágenes de portada"
        ordering = ["orden", "id"]

    def __str__(self):
        return self.descripcion or self.imagen.name


class Categoria(models.Model):
    """Agrupación de cursos, tal como se muestra en la web (Cargas Generales, etc.)."""

    nombre = models.CharField("nombre", max_length=120, unique=True)
    slug = models.SlugField("identificador en la URL", max_length=140, unique=True, blank=True)
    resumen = models.TextField("resumen", blank=True, help_text="Bajada que aparece bajo el título.")
    icono = models.FileField(
        "icono",
        upload_to="iconos/",
        blank=True,
        validators=[FileExtensionValidator(["svg", "png", "webp"])],
        help_text=(
            "Se muestra junto al título de la categoría en la web. "
            "Preferentemente SVG; también sirve PNG o WebP de 64×64."
        ),
    )
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

        con_mes = "j \\d\\e F"
        fin = self.fecha_fin
        if not fin or fin == self.fecha_inicio:
            return date_format(self.fecha_inicio, con_mes, use_l10n=True)
        # «5 al 7 de octubre»: el mes se escribe una sola vez si no cambia.
        mismo_mes = (fin.year, fin.month) == (self.fecha_inicio.year, self.fecha_inicio.month)
        inicio = date_format(self.fecha_inicio, "j" if mismo_mes else con_mes, use_l10n=True)
        return f"{inicio} al {date_format(fin, con_mes, use_l10n=True)}"

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
