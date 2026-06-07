from django.urls import path

from apps.travel_quiz.views.travel_quiz_views import QuizSubmitView

urlpatterns = [
    path("quiz/submit", QuizSubmitView.as_view(), name="quiz_submit"),
]
