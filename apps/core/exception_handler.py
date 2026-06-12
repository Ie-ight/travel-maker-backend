from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is not None and "error_detail" not in response.data:
        detail = response.data.pop("detail", None)
        response.data = {"error_detail": detail if detail is not None else response.data}
    return response
