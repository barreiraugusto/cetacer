from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    # Sesión
    path(
        "ingresar/",
        auth_views.LoginView.as_view(
            template_name="panel/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),

    # Tablero
    path("", views.inicio, name="inicio"),
    path("agenda/", views.agenda, name="agenda"),

    # Catálogo
    path("cursos/", views.cursos_lista, name="cursos"),
    path("cursos/nuevo/", views.curso_editar, name="curso_nuevo"),
    path("cursos/<int:pk>/", views.curso_editar, name="curso_editar"),
    path("cursos/<int:pk>/eliminar/", views.curso_eliminar, name="curso_eliminar"),
    path("categorias/", views.categorias_lista, name="categorias"),
    path("categorias/nueva/", views.categoria_editar, name="categoria_nueva"),
    path("categorias/<int:pk>/", views.categoria_editar, name="categoria_editar"),

    # Comisiones
    path("comisiones/", views.comisiones_lista, name="comisiones"),
    path("comisiones/nueva/", views.comision_editar, name="comision_nueva"),
    path("comisiones/<int:pk>/", views.comision_detalle, name="comision_detalle"),
    path("comisiones/<int:pk>/editar/", views.comision_editar, name="comision_editar"),
    path("comisiones/<int:pk>/estado/", views.comision_cambiar_estado, name="comision_estado"),
    path("comisiones/<int:pk>/inscribir/", views.inscribir, name="inscribir"),
    path("comisiones/<int:pk>/asistencia/", views.tomar_asistencia, name="asistencia"),
    path("comisiones/<int:pk>/exportar/", views.exportar_comision, name="exportar_comision"),
    path("comisiones/<int:pk>/planilla/", views.planilla_asistencia, name="planilla"),

    # Inscripciones y personas
    path("inscripciones/", views.inscripciones_lista, name="inscripciones"),
    path("inscripciones/<int:pk>/", views.inscripcion_editar, name="inscripcion_editar"),
    path("inscripciones/exportar/", views.exportar_inscripciones, name="exportar_inscripciones"),
    path("participantes/", views.participantes_lista, name="participantes"),
    path("participantes/nuevo/", views.participante_editar, name="participante_nuevo"),
    path("participantes/<int:pk>/", views.participante_editar, name="participante_editar"),
    path("participantes/exportar/", views.exportar_participantes, name="exportar_participantes"),
    path("empresas/", views.empresas_lista, name="empresas"),
    path("empresas/nueva/", views.empresa_editar, name="empresa_nueva"),
    path("empresas/<int:pk>/", views.empresa_editar, name="empresa_editar"),

    # Informes
    path("informes/", views.informes, name="informes"),

    # Administración
    path("usuarios/", views.usuarios_lista, name="usuarios"),
    path("usuarios/nuevo/", views.usuario_editar, name="usuario_nuevo"),
    path("usuarios/<int:pk>/", views.usuario_editar, name="usuario_editar"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("ayuda/", views.ayuda, name="ayuda"),
]
