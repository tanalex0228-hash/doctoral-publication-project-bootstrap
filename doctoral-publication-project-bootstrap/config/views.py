import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse


logger = logging.getLogger(__name__)


def healthz(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        logger.error("healthcheck_database_unavailable")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
