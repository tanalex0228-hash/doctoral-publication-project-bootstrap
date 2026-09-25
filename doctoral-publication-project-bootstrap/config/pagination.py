from django.core.paginator import Paginator


DEFAULT_PAGE_SIZE = 25


def paginate_queryset(request, queryset, *, page_size=DEFAULT_PAGE_SIZE):
    """Return a safe page and query string suitable for pagination links."""
    parameters = request.GET.copy()
    parameters.pop("page", None)
    return Paginator(queryset, page_size).get_page(request.GET.get("page")), parameters.urlencode()
