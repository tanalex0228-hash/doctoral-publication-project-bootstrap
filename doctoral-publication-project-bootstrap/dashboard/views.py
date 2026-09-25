from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from config.pagination import paginate_queryset
from advising.models import StudentAdvisor
from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor
from publications.models import PublicationRecord
from publications.permissions import is_advisor_actor, visible_publications_for
from publications.querysets import official_publications


@login_required
def student_dashboard(request):
    try:
        student = request.user.doctoral_profile
    except DoctoralStudentProfile.DoesNotExist as error:
        raise Http404("Student profile not found.") from error
    publications = PublicationRecord.objects.filter(owner_student=student).select_related("publication_type").order_by("-updated_at")
    statuses = PublicationRecord.WorkflowStatus
    return render(request, "dashboard/student_dashboard.html", {
        "student": student,
        "drafts": publications.filter(workflow_status=statuses.DRAFT),
        "submitted": publications.filter(workflow_status=statuses.SUBMITTED),
        "returned": publications.filter(workflow_status=statuses.RETURNED),
        "approved": official_publications().filter(owner_student=student),
    })


def _advisor_professor(request):
    if not is_advisor_actor(request.user):
        raise Http404("Advisor resource not found.")
    try:
        professor = request.user.professor_profile
    except Professor.DoesNotExist as error:
        raise Http404("Advisor profile not found.") from error
    if professor.status != Professor.Status.ACTIVE:
        raise Http404("Advisor resource not found.")
    return professor


def _active_advisee(professor, student_id):
    relation = get_object_or_404(
        StudentAdvisor.objects.select_related("student", "student__user").filter(
            professor=professor,
            is_active=True,
        ),
        student_id=student_id,
    )
    return relation.student


def _advisor_publications(user, student):
    publications = visible_publications_for(user, include_staff_scope=False)
    if student is not None:
        publications = publications.filter(owner_student=student)
    return publications.select_related(
        "owner_student", "publication_type"
    ).prefetch_related(
        "authors",
        "indices",
        "research_fields",
        "documents",
        "owner_student__advisor_relations__professor",
    )


@login_required
def advisor_dashboard(request):
    professor = _advisor_professor(request)
    advisee_relations = StudentAdvisor.objects.filter(professor=professor, is_active=True).select_related(
        "student", "student__user"
    ).order_by("student__student_number").distinct()
    page_obj, pagination_query = paginate_queryset(request, advisee_relations)
    return render(request, "dashboard/advisor_dashboard.html", {
        "professor": professor,
        "advisee_relations": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    })


@login_required
def advisor_advisee_publications(request, student_id):
    professor = _advisor_professor(request)
    student = _active_advisee(professor, student_id)
    publications = _advisor_publications(request.user, student).order_by("-updated_at")
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "dashboard/advisor_advisee_publications.html", {
        "professor": professor,
        "student": student,
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    })


@login_required
def advisor_publication_detail(request, publication_id):
    professor = _advisor_professor(request)
    publication = get_object_or_404(
        _advisor_publications(request.user, None).filter(
            owner_student__advisor_relations__professor=professor,
            owner_student__advisor_relations__is_active=True,
        ),
        pk=publication_id,
    )
    return render(request, "dashboard/advisor_publication_detail.html", {
        "professor": professor,
        "publication": publication,
        "documents": [document for document in publication.documents.all() if document.is_active],
    })
