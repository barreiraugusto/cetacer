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
    path("paginas/", views.paginas_lista, name="paginas"),
    path("paginas/nueva/", views.pagina_editar, name="pagina_nueva"),
    path("paginas/<int:pk>/", views.pagina_editar, name="pagina_editar"),
    path("paginas/<int:pk>/eliminar/", views.pagina_eliminar, name="pagina_eliminar"),

    # Comisiones
    path("comisiones/", views.comisiones_lista, name="comisiones"),
    path("comisiones/nueva/", views.comision_editar, name="comision_nueva"),
    path("comisiones/<int:pk>/editar/", views.comision_editar, name="comision_editar"),
    path("comisiones/<int:pk>/estado/", views.comision_cambiar_estado, name="comision_estado"),
    path("comisiones/<int:pk>/eliminar/", views.comision_eliminar, name="comision_eliminar"),

    # Administración
    path("usuarios/", views.usuarios_lista, name="usuarios"),
    path("usuarios/nuevo/", views.usuario_editar, name="usuario_nuevo"),
    path("usuarios/<int:pk>/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/eliminar/", views.usuario_eliminar, name="usuario_eliminar"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("ayuda/", views.ayuda, name="ayuda"),
]
