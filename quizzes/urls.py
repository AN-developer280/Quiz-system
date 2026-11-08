from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    # teacher
    path("teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/quizzes/generate/", views.quiz_generate, name="quiz_generate"),
    path("teacher/quizzes/<int:pk>/", views.quiz_detail, name="quiz_detail"),
    path("teacher/quizzes/<int:pk>/edit/", views.quiz_edit, name="quiz_edit"),
    path("teacher/quizzes/<int:pk>/delete/", views.quiz_delete, name="quiz_delete"),
    path("teacher/quizzes/<int:pk>/publish/", views.quiz_publish, name="quiz_publish"),
    path("teacher/quizzes/<int:pk>/unpublish/", views.quiz_unpublish, name="quiz_unpublish"),
    path("teacher/quizzes/<int:pk>/ai-more/", views.quiz_add_ai_questions, name="quiz_add_ai"),
    path("teacher/quizzes/<int:pk>/questions/add/", views.question_add, name="question_add"),
    path("teacher/quizzes/<int:pk>/questions/<int:qpk>/edit/", views.question_edit, name="question_edit"),
    path("teacher/quizzes/<int:pk>/questions/<int:qpk>/delete/", views.question_delete, name="question_delete"),
    path("teacher/quizzes/<int:pk>/results/", views.quiz_results, name="quiz_results"),
    path("teacher/attempts/<int:pk>/", views.teacher_attempt_detail, name="teacher_attempt"),
    # student
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("student/quizzes/<int:pk>/take/", views.quiz_take, name="quiz_take"),
    path("student/attempts/<int:pk>/", views.student_result, name="student_result"),
]
