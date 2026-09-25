import csv

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from config.pagination import paginate_queryset
from doctoral_students.models import DoctoralStudentProfile
from publications.permissions import is_staff_actor
from .forms import StatisticsFilterForm
from .services import (
    STUDENT_SORTS,
    approved_publications_for_student,
    csv_safe_cell,
    export_ready_publications,
    export_ready_rows,
    filtered_approved_publications,
    statistics_overview,
    student_statistics_table,
)


def _require_statistics_role(request):
    if not is_staff_actor(request.user):
        raise Http404("Statistics resource not found.")


def _filtered_records(request):
    form = StatisticsFilterForm(request.GET or None)
    if not form.is_valid():
        return form, filtered_approved_publications()
    return form, filtered_approved_publications(**form.cleaned_data)


@login_required
def statistics_dashboard(request):
    _require_statistics_role(request)
    form, records = _filtered_records(request)
    return render(request, "statistics/dashboard.html", {
        "filter_form": form,
        "overview": statistics_overview(records),
    })


@login_required
def student_statistics(request):
    _require_statistics_role(request)
    form, records = _filtered_records(request)
    requested_sort = request.GET.get("sort", "name")
    sort = requested_sort if requested_sort in STUDENT_SORTS else "name"
    students = student_statistics_table(records, sort=sort)
    page_obj, pagination_query = paginate_queryset(request, students)
    return render(request, "statistics/student_list.html", {
        "filter_form": form,
        "students": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "sort": sort,
    })


@login_required
def student_statistics_detail(request, student_id):
    _require_statistics_role(request)
    student = get_object_or_404(DoctoralStudentProfile, pk=student_id)
    publications = approved_publications_for_student(student)
    return render(request, "statistics/student_detail.html", {
        "student": student,
        "publications": publications,
    })


@login_required
def export_ready_data(request):
    _require_statistics_role(request)
    form, records = _filtered_records(request)
    publications = export_ready_publications(records)
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "statistics/export_ready.html", {
        "filter_form": form,
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    })


@login_required
def csv_export(request):
    _require_statistics_role(request)
    form, records = _filtered_records(request)
    if not form.is_valid():
        records = records.none()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="approved-publications.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "Student", "Student ID", "Advisors", "Publication Title", "Publication Type",
        "Publication Index", "Research Field", "Authors", "Journal / Conference",
        "Publication Date", "Acceptance Date", "DOI", "ISSN", "Language", "Approved Date",
        "Visibility", "Publishing State",
    ])
    for row in export_ready_rows(records):
        writer.writerow([csv_safe_cell(value) for value in row])
    return response
