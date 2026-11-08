from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def teacher_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_teacher:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def student_required(view):
    """Logged-in student whose status is APPROVED (checked on every request)."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_student:
            raise PermissionDenied
        if not user.is_approved:
            logout(request)
            messages.error(request, "Your account is not approved by your teacher, so access is blocked.")
            return redirect("login")
        return view(request, *args, **kwargs)

    return wrapper
