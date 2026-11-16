from django.urls import path
from . import views

app_name = "review"
urlpatterns = [
    path("queue/", views.review_queue, name="queue"),
    path("journals/", views.journal_list, name="journal_list"),
    path("conferences/", views.conference_list, name="conference_list"),
    path("archive/", views.archive_list, name="archive_list"),
    path("publications/<uuid:publication_id>/", views.review_detail, name="detail"),
    path("publications/<uuid:publication_id>/approve/", views.approve, name="approve"),
    path("publications/<uuid:publication_id>/return/", views.return_publication, name="return_publication"),
    path("publications/trash/", views.trash_selected, name="trash_selected"),
    path("publications/<uuid:publication_id>/archive/", views.archive, name="archive"),
    path("publications/<uuid:publication_id>/revoke-approval/", views.revoke, name="revoke"),
    path("publications/<uuid:publication_id>/settings/", views.publication_settings, name="settings"),
]
