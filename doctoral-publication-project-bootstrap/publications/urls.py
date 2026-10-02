from django.urls import path
from . import views

app_name = "publications"
urlpatterns = [
    path("journal/new/", views.publication_typed_create, {"kind": "journal"}, name="journal_create"),
    path("conference/new/", views.publication_typed_create, {"kind": "conference"}, name="conference_create"),
    path("new/", views.publication_create, name="create"),
    path("<uuid:publication_id>/", views.publication_detail, name="detail"),
    path("journal/<uuid:publication_id>/edit/", views.publication_typed_edit, {"kind": "journal"}, name="journal_edit"),
    path("conference/<uuid:publication_id>/edit/", views.publication_typed_edit, {"kind": "conference"}, name="conference_edit"),
    path("<uuid:publication_id>/edit/", views.publication_edit, name="edit"),
    path("<uuid:publication_id>/journal-detail/", views.journal_detail_edit, name="journal_detail_edit"),
    path("<uuid:publication_id>/conference-detail/", views.conference_detail_edit, name="conference_detail_edit"),
    path("<uuid:publication_id>/authors/new/", views.author_create, name="author_create"),
    path("<uuid:publication_id>/authors/<uuid:author_id>/edit/", views.author_edit, name="author_edit"),
    path("<uuid:publication_id>/authors/<uuid:author_id>/delete/", views.author_delete, name="author_delete"),
    path("<uuid:publication_id>/authors/<uuid:author_id>/move/<str:direction>/", views.author_move, name="author_move"),
    path("<uuid:publication_id>/submit/", views.publication_submit, name="submit"),
    path("<uuid:publication_id>/withdraw/", views.publication_withdraw, name="withdraw"),
    path("<uuid:publication_id>/revisions/new/", views.publication_revision_create, name="revision_create"),
]
