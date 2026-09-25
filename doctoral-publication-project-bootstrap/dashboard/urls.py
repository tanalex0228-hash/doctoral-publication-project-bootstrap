from django.urls import path
from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.student_dashboard, name="student"),
    path("advisor/", views.advisor_dashboard, name="advisor"),
    path("advisor/students/<uuid:student_id>/", views.advisor_advisee_publications, name="advisor_advisee_publications"),
    path("advisor/publications/<uuid:publication_id>/", views.advisor_publication_detail, name="advisor_publication_detail"),
]
