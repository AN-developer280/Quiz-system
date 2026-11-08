from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .decorators import teacher_required
from .forms import LoginForm, RejectForm, StudentRegistrationForm, TeacherRegistrationForm
from .models import User


def home(request):
    u = request.user
    if u.is_authenticated:
        if u.is_teacher:
            return redirect("quizzes:teacher_dashboard")
        return redirect("quizzes:student_dashboard")
    return render(request, "accounts/home.html")


class CustomLoginView(auth_views.LoginView):
    form_class = LoginForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True


def register_teacher(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = TeacherRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Teacher account created. Please log in.")
        return redirect("login")
    return render(request, "accounts/register_teacher.html", {"form": form})


def register_student(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student = form.save()  # saved immediately with status=PENDING
        services.notify_teacher_new_student(student, request)
        return redirect("register_student_submitted")
    return render(request, "accounts/register_student.html", {"form": form})


def register_student_submitted(request):
    return render(request, "accounts/student_submitted.html")


# ------------------------------------------------- teacher reviews students
def _my_student(request, pk):
    return get_object_or_404(User, pk=pk, role=User.Role.STUDENT, teacher=request.user)


@teacher_required
def student_requests(request):
    status = request.GET.get("status", "PENDING")
    if status not in User.Status.values:
        status = "PENDING"
    mine = User.objects.filter(role=User.Role.STUDENT, teacher=request.user)
    counts = {s: mine.filter(status=s).count() for s in User.Status.values}
    return render(
        request,
        "teacher/students.html",
        {"students": mine.filter(status=status).order_by("-date_joined"), "current": status, "counts": counts},
    )


@teacher_required
def student_detail(request, pk):
    return render(request, "teacher/student_detail.html", {"s": _my_student(request, pk), "reject_form": RejectForm()})


@teacher_required
@require_POST
def student_approve(request, pk):
    student = _my_student(request, pk)
    if student.is_approved:
        messages.info(request, "This student is already approved.")
    else:
        sent = services.approve_student(student, request)
        messages.success(
            request,
            f"{student.display_name} approved. "
            + ("Approval email sent." if sent else "Email could NOT be sent - check email settings."),
        )
    return redirect("student_requests")


@teacher_required
@require_POST
def student_reject(request, pk):
    student = _my_student(request, pk)
    form = RejectForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    if student.is_rejected:
        messages.info(request, "This student is already rejected.")
    else:
        sent = services.reject_student(student, reason, request)
        messages.success(
            request,
            f"{student.display_name} rejected. "
            + ("Rejection email sent." if sent else "Email could NOT be sent - check email settings."),
        )
    return redirect("student_requests")
