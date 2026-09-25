from django.urls import path

from . import views

app_name = "public_site"

urlpatterns = [
    path("", views.publication_list, name="publication_list"),
    path("department/", views.department_publication_list, name="department_list"),
    path("public/<uuid:publication_id>/", views.publication_detail, name="publication_detail"),
    path("department/<uuid:publication_id>/", views.department_publication_detail, name="department_detail"),
]
