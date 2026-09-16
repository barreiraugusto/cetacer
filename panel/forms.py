"""Formularios del panel.

Todos los widgets llevan la clase `campo` para que el CSS del panel los tome
sin repetir estilos por plantilla.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory

from contenido.models import EnlacePagina, Pagina
from cuentas.models import JERARQUIA, Rol, Usuario
from cursos.models import Categoria, Comision, ConfiguracionSitio, Curso
from inscripciones.models import Empresa, Inscripcion, Participante


class BaseForm(forms.ModelForm):
    """Aplica las clases del panel a todos los widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "casilla")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "campo campo--select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "campo")
                widget.attrs.setdefault("rows", 3)
            else:
                widget.attrs.setdefault("class", "campo")
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"
            if isinstance(widget, forms.TimeInput):
                widget.input_type = "time"


class CategoriaForm(BaseForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "resumen", "orden", "activa"]


class CursoForm(BaseForm):
    class Meta:
        model = Curso
        fields = [
            "categoria", "nombre", "precio", "precio_a_consultar", "duracion_horario",
            "cupo_sugerido", "cupo_texto", "requisitos", "descripcion", "link_externo",
            "orden", "activo",
        ]
        help_texts = {
            "precio": "Sólo el número. Ej: 405000",
        }

    def clean(self):
        datos = super().clean()
        if not datos.get("precio_a_consultar") and datos.get("precio") in (None, ""):
            self.add_error(
                "precio",
                "Poné un precio o marcá «mostrar Consultar» para que la web no quede vacía.",
            )
        return datos


class ComisionForm(BaseForm):
    class Meta:
        model = Comision
        fields = [
            "curso", "fecha_inicio", "fecha_fin", "hora_inicio", "hora_fin",
            "cupo", "lugar", "instructor", "estado", "observaciones",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = Curso.objects.select_related("categoria")
        self.fields["instructor"].queryset = Usuario.objects.filter(
            is_active=True, groups__name=Rol.INSTRUCTOR.value
        ).distinct()
        self.fields["instructor"].empty_label = "Sin asignar"

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
        if inicio and fin and fin < inicio:
            self.add_error("fecha_fin", "La fecha de fin no puede ser anterior al inicio.")
        h1, h2 = datos.get("hora_inicio"), datos.get("hora_fin")
        if h1 and h2 and h2 <= h1:
            self.add_error("hora_fin", "El horario de fin debe ser posterior al de inicio.")
        cupo = datos.get("cupo")
        if self.instance.pk and cupo is not None:
            ocupados = self.instance.cantidad_inscriptos
            if cupo < ocupados:
                self.add_error(
                    "cupo",
                    f"Ya hay {ocupados} inscriptos en esta comisión: el cupo no puede ser menor.",
                )
        return datos


class EmpresaForm(BaseForm):
    class Meta:
        model = Empresa
        fields = ["razon_social", "cuit", "telefono", "email", "localidad", "socia", "notas"]


class ParticipanteForm(BaseForm):
    class Meta:
        model = Participante
        fields = [
            "dni", "apellido", "nombre", "fecha_nacimiento", "telefono", "email",
            "localidad", "empresa", "categoria_licencia", "observaciones",
        ]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"})}

    def clean_dni(self):
        return (self.cleaned_data["dni"] or "").replace(".", "").replace(" ", "").strip()


class InscripcionForm(BaseForm):
    class Meta:
        model = Inscripcion
        fields = [
            "estado", "pago", "monto", "comprobante",
            "psicofisico_vigente", "documentacion_completa", "notas",
        ]


class InscribirForm(forms.Form):
    """Alta rápida desde la ficha de la comisión: busca el DNI o crea la persona."""

    dni = forms.CharField(label="DNI", max_length=12, widget=forms.TextInput(
        attrs={"class": "campo", "placeholder": "Sin puntos", "autofocus": "autofocus"}))
    apellido = forms.CharField(label="Apellido", max_length=120, required=False,
        widget=forms.TextInput(attrs={"class": "campo"}))
    nombre = forms.CharField(label="Nombre", max_length=120, required=False,
        widget=forms.TextInput(attrs={"class": "campo"}))
    telefono = forms.CharField(label="Teléfono", max_length=40, required=False,
        widget=forms.TextInput(attrs={"class": "campo"}))
    email = forms.EmailField(label="Correo", required=False,
        widget=forms.EmailInput(attrs={"class": "campo"}))
    empresa = forms.ModelChoiceField(
        label="Empresa", queryset=Empresa.objects.all(), required=False,
        empty_label="Sin empresa", widget=forms.Select(attrs={"class": "campo campo--select"}))
    estado = forms.ChoiceField(
        label="Estado", choices=Inscripcion.Estado.choices,
        initial=Inscripcion.Estado.CONFIRMADA,
        widget=forms.Select(attrs={"class": "campo campo--select"}))
    pago = forms.ChoiceField(
        label="Pago", choices=Inscripcion.Pago.choices, initial=Inscripcion.Pago.PENDIENTE,
        widget=forms.Select(attrs={"class": "campo campo--select"}))

    def clean_dni(self):
        return (self.cleaned_data["dni"] or "").replace(".", "").replace(" ", "").strip()

    def clean(self):
        datos = super().clean()
        dni = datos.get("dni")
        if dni and not Participante.objects.filter(dni=dni).exists():
            # Persona nueva: hace falta el nombre para poder darla de alta.
            if not datos.get("apellido") or not datos.get("nombre"):
                raise forms.ValidationError(
                    "Ese DNI no está registrado. Completá apellido y nombre para darlo de alta."
                )
        return datos


class ConfiguracionForm(BaseForm):
    class Meta:
        model = ConfiguracionSitio
        exclude = []


class UsuarioForm(BaseForm):
    """Alta y edición de usuarios del panel, con el rol como un único desplegable."""

    rol = forms.ChoiceField(
        label="Rol en el panel",
        choices=[(r.value, r.label) for r in JERARQUIA],
        widget=forms.Select(attrs={"class": "campo campo--select"}),
    )
    password1 = forms.CharField(
        label="Contraseña", required=False, widget=forms.PasswordInput(attrs={"class": "campo"}),
        help_text="Al editar, dejalo vacío para no cambiarla.",
    )
    password2 = forms.CharField(
        label="Repetir contraseña", required=False,
        widget=forms.PasswordInput(attrs={"class": "campo"}),
    )

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "telefono", "dni", "cargo", "is_active"]
        labels = {"username": "Usuario", "first_name": "Nombre", "last_name": "Apellido"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            rol = self.instance.rol
            if rol:
                self.fields["rol"].initial = rol.value
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Las dos contraseñas no coinciden.")
            elif len(p1) < 8:
                self.add_error("password1", "Usá al menos 8 caracteres.")
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        clave = self.cleaned_data.get("password1")
        if clave:
            usuario.set_password(clave)
        usuario.is_staff = False
        if commit:
            usuario.save()
            usuario.asignar_rol(self.cleaned_data["rol"])
        return usuario


class PreinscripcionForm(forms.Form):
    """Formulario público. No expone estados internos ni montos."""

    comision = forms.ModelChoiceField(
        label="Fecha a la que querés asistir", queryset=Comision.objects.none(),
        empty_label="Elegí una fecha",
    )
    dni = forms.CharField(label="DNI", max_length=12)
    apellido = forms.CharField(label="Apellido", max_length=120)
    nombre = forms.CharField(label="Nombre", max_length=120)
    telefono = forms.CharField(label="Teléfono / WhatsApp", max_length=40)
    email = forms.EmailField(label="Correo electrónico", required=False)
    localidad = forms.CharField(label="Localidad", max_length=120, required=False)
    empresa = forms.CharField(
        label="Empresa donde trabajás", max_length=200, required=False,
        help_text="Opcional. Si trabajás por tu cuenta, dejalo vacío.",
    )

    def __init__(self, curso, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curso = curso
        self.fields["comision"].queryset = curso.comisiones_publicadas()
        for nombre, campo in self.fields.items():
            campo.widget.attrs.setdefault("class", "campo-web")

    def clean_dni(self):
        dni = (self.cleaned_data["dni"] or "").replace(".", "").replace(" ", "").strip()
        if not dni.isdigit() or not (6 <= len(dni) <= 12):
            raise forms.ValidationError("Ingresá el DNI sin puntos ni espacios.")
        return dni

    def clean(self):
        datos = super().clean()
        comision, dni = datos.get("comision"), datos.get("dni")
        if comision:
            if comision.completa:
                self.add_error(
                    "comision",
                    "Esa fecha ya está completa. Elegí otra o escribinos por WhatsApp.",
                )
            elif dni and comision.inscripciones.filter(participante__dni=dni).exists():
                self.add_error(
                    "dni", "Ya tenemos una solicitud tuya para esa fecha. Te vamos a contactar."
                )
        return datos


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
