from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from config.pagination import paginate_queryset
from publications.permissions import (
    department_portal_publications_for,
    is_department_member,
    public_portal_publications,
)
from .forms import PortalFilterForm
from .services import PORTAL_SORTS, portal_publications


def _public_portal_removed():
    """The simplified product has no anonymous or department portal surface."""
    raise Http404("Public publication resources are not enabled.")


def _portal_records(request, queryset):
    # Bind an empty QueryDict as well, so an unfiltered portal list is valid.
    form = PortalFilterForm(request.GET)
    requested_sort = request.GET.get("sort", "publication_date")
    sort = requested_sort if requested_sort in PORTAL_SORTS else "publication_date"
    if not form.is_valid():
        return form, queryset.none(), sort
    return form, portal_publications(queryset, sort=sort, **form.cleaned_data), sort


def publication_list(request):
    _public_portal_removed()
    form, publications, sort = _portal_records(request, public_portal_publications())
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "public_site/publication_list.html", {
        "filter_form": form,
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "sort": sort,
        "detail_route": "public_site:publication_detail",
        "portal_title": "公開成果",
        "portal_note": "僅列出已核准、已發佈且設定為公開的成果 metadata。",
        "can_access_department_portal": is_department_member(request.user),
    })


def publication_detail(request, publication_id):
    _public_portal_removed()
    publication = get_object_or_404(
        public_portal_publications().select_related("publication_type").prefetch_related(
            "authors", "indices", "research_fields"
        ),
        pk=publication_id,
    )
    return render(request, "public_site/publication_detail.html", {
        "publication": publication,
        "list_route": "public_site:publication_list",
        "portal_title": "公開成果",
    })


def department_publication_list(request):
    _public_portal_removed()
    if not is_department_member(request.user):
        raise Http404("Department resource not found.")
    form, publications, sort = _portal_records(request, department_portal_publications_for(request.user))
    page_obj, pagination_query = paginate_queryset(request, publications)
    return render(request, "public_site/publication_list.html", {
        "filter_form": form,
        "publications": page_obj,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "sort": sort,
        "detail_route": "public_site:department_detail",
        "portal_title": "系所成果",
        "portal_note": "僅列出已核准、已發佈且授權系所檢視的成果 metadata。",
        "can_access_department_portal": True,
    })


def department_publication_detail(request, publication_id):
    _public_portal_removed()
    if not is_department_member(request.user):
        raise Http404("Department resource not found.")
    publication = get_object_or_404(
        department_portal_publications_for(request.user).select_related("publication_type").prefetch_related(
            "authors", "indices", "research_fields"
        ),
        pk=publication_id,
    )
    return render(request, "public_site/publication_detail.html", {
        "publication": publication,
        "list_route": "public_site:department_list",
        "portal_title": "系所成果",
    })
