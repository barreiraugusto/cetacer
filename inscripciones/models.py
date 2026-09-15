from django.core.validators import RegexValidator
from django.db import models

solo_digitos = RegexValidator(r"^\d{6,12}$", "Ingresá el DNI sin puntos ni espacios.")


class Empresa(models.Model):
    """Empresa de transporte que envía participantes a los cursos."""

    razon_social = models.CharField("razón social", max_length=200, unique=True)
    cuit = models.CharField("CUIT", max_length=20, blank=True)
    telefono = models.CharField("teléfono", max_length=40, blank=True)
    email = models.EmailField("correo", blank=True)
    localidad = models.CharField("localidad", max_length=120, blank=True)
    socia = models.BooleanField(
        "empresa asociada a CETACER", default=False,
        help_text="Se usa para separar el listado de asociadas en los informes.",
    )
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        ordering = ["razon_social"]

    def __str__(self):
        return self.razon_social


class Participante(models.Model):
    """Persona que cursa. Se identifica por DNI y se reutiliza entre cursos."""

    dni = models.CharField("DNI", max_length=12, unique=True, validators=[solo_digitos])
    apellido = models.CharField("apellido", max_length=120)
    nombre = models.CharField("nombre", max_length=120)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    telefono = models.CharField("teléfono", max_length=40, blank=True)
    email = models.EmailField("correo", blank=True)
    localidad = models.CharField("localidad", max_length=120, blank=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="participantes", verbose_name="empresa",
    )
    categoria_licencia = models.CharField(
        "categoría de licencia", max_length=40, blank=True,
        help_text="Ej: C, D.2, E.1",
    )
    observaciones = models.TextField("observaciones", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "participante"
        verbose_name_plural = "participantes"
        ordering = ["apellido", "nombre"]
        indexes = [models.Index(fields=["apellido", "nombre"])]

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"

    @property
    def nombre_completo(self):
        return f"{self.apellido}, {self.nombre}"

    @property
    def cursos_realizados(self):
        return self.inscripciones.filter(estado=Inscripcion.Estado.ASISTIO).count()


class Inscripcion(models.Model):
    """Vincula a un participante con una comisión concreta."""

    class Estado(models.TextChoices):
        PREINSCRIPTO = "preinscripta", "Preinscripto"
        CONFIRMADA = "confirmada", "Confirmado"
        ASISTIO = "asistio", "Asistió"
        AUSENTE = "ausente", "Ausente"
        CANCELADA = "cancelada", "Cancelada"

    class Pago(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADO = "pagado", "Pagado"
        EXENTO = "exento", "Exento"

    comision = models.ForeignKey(
        "cursos.Comision", on_delete=models.CASCADE,
        related_name="inscripciones", verbose_name="comisión",
    )
    participante = models.ForeignKey(
        Participante, on_delete=models.CASCADE,
        related_name="inscripciones", verbose_name="participante",
    )
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.PREINSCRIPTO
    )
    pago = models.CharField(
        "pago", max_length=20, choices=Pago.choices, default=Pago.PENDIENTE
    )
    monto = models.DecimalField(
        "monto abonado", max_digits=12, decimal_places=2, null=True, blank=True
    )
    comprobante = models.CharField(
        "comprobante", max_length=100, blank=True,
        help_text="Número de boleta e-SICAPRO o recibo interno.",
    )
    psicofisico_vigente = models.BooleanField("psicofísico vigente", default=False)
    documentacion_completa = models.BooleanField("documentación completa", default=False)
    notas = models.TextField("notas", blank=True)
    origen = models.CharField(
        "origen", max_length=20,
        choices=[("panel", "Carga interna"), ("web", "Formulario web"), ("whatsapp", "WhatsApp")],
        default="panel",
    )
    creado_por = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inscripciones_cargadas", verbose_name="cargada por",
    )
    creado = models.DateTimeField("fecha de inscripción", auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "inscripción"
        verbose_name_plural = "inscripciones"
        ordering = ["participante__apellido", "participante__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["comision", "participante"], name="participante_unico_por_comision"
            )
        ]
        indexes = [models.Index(fields=["estado", "pago"])]

    def __str__(self):
        return f"{self.participante} — {self.comision.curso.nombre}"

    @property
    def ocupa_cupo(self):
        return self.estado != self.Estado.CANCELADA

    @property
    def lista_para_cursar(self):
        return (
            self.estado == self.Estado.CONFIRMADA
            and self.pago in {self.Pago.PAGADO, self.Pago.EXENTO}
            and self.documentacion_completa
        )

    @property
    def pendientes(self):
        """Qué le falta a esta inscripción para quedar lista. Se muestra en el panel."""
        faltas = []
        if self.pago == self.Pago.PENDIENTE:
            faltas.append("pago")
        if not self.psicofisico_vigente:
            faltas.append("psicofísico")
        if not self.documentacion_completa:
            faltas.append("documentación")
        return faltas
