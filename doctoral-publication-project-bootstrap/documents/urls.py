from django.urls import path
from . import views

app_name = "documents"
urlpatterns = [
    path("publications/<uuid:publication_id>/upload/", views.document_upload, name="upload"),
    path("publications/<uuid:publication_id>/documents/<uuid:document_id>/replace/", views.document_replace, name="replace"),
    path("publications/<uuid:publication_id>/documents/<uuid:document_id>/remove/", views.document_remove, name="remove"),
    path("documents/<uuid:document_id>/download/", views.document_download, name="download"),
]
