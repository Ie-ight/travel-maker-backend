from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, ValueError):
        return Response({"error_detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    response = exception_handler(exc, context)
    if response is not None and "error_detail" not in response.data:
        detail = response.data.pop("detail", None)
        response.data = {"error_detail": detail if detail is not None else response.data}
    return response
