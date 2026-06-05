from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class PlaceSortByVectorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        # TODO: add @extend_schema decorator from schemas/sort_algorithm_schemas.py
        raise NotImplementedError
