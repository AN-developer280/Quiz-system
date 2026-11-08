from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/teacher/", views.register_teacher, name="register_teacher"),
    path("register/student/", views.register_student, name="register_student"),
    path("register/student/submitted/", views.register_student_submitted, name="register_student_submitted"),
    # teacher reviews his students
    path("teacher/students/", views.student_requests, name="student_requests"),
    path("teacher/students/<int:pk>/", views.student_detail, name="student_detail"),
    path("teacher/students/<int:pk>/approve/", views.student_approve, name="student_approve"),
    path("teacher/students/<int:pk>/reject/", views.student_reject, name="student_reject"),
]
