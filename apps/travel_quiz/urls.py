from django.urls import path

from apps.travel_quiz.views.travel_quiz_views import (
    QuizAvatarView,
    QuizResultView,
    QuizSubmitView,
    SharedQuizResultView,
)

urlpatterns = [
    path("quiz/submit", QuizSubmitView.as_view(), name="quiz_submit"),
    path("quiz/result/shared", SharedQuizResultView.as_view(), name="quiz_result_shared"),
    path("users/quiz/result", QuizResultView.as_view(), name="quiz_result"),
    path("users/avatar", QuizAvatarView.as_view(), name="quiz_avatar"),
]
