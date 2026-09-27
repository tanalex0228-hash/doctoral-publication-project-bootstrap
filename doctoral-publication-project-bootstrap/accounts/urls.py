from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("home/", views.home_view, name="home"),
    path("profile/", views.profile_view, name="profile"),
    path("password/change/", views.password_change_view, name="password_change"),
]
