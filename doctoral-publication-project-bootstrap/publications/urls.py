from django.urls import path
from . import views

app_name = "publications"
urlpatterns = [
    path("new/", views.publication_create, name="create"),
    path("<uuid:publication_id>/", views.publication_detail, name="detail"),
    path("<uuid:publication_id>/edit/", views.publication_edit, name="edit"),
    path("<uuid:publication_id>/authors/new/", views.author_create, name="author_create"),
    path("<uuid:publication_id>/authors/<uuid:author_id>/edit/", views.author_edit, name="author_edit"),
    path("<uuid:publication_id>/authors/<uuid:author_id>/delete/", views.author_delete, name="author_delete"),
    path("<uuid:publication_id>/authors/<uuid:author_id>/move/<str:direction>/", views.author_move, name="author_move"),
    path("<uuid:publication_id>/submit/", views.publication_submit, name="submit"),
]
