from django.urls import path

from apps.travel_quiz.views.travel_quiz_views import QuizResultView, QuizSubmitView

urlpatterns = [
    path("quiz/submit", QuizSubmitView.as_view(), name="quiz_submit"),
    path("users/quiz/result", QuizResultView.as_view(), name="quiz_result"),
]
