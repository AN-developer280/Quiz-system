"""Student approval workflow: status updates + emails.

The student record is saved at registration. Approve/reject only update that
same record and then email the address already stored in it.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _abs(request, name, *args):
    path = reverse(name, args=args)
    return request.build_absolute_uri(path) if request else path


def _send(subject, body, recipients):
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        return True
    except Exception:  # SMTP problems must not break the workflow
        logger.exception("Could not send email to %s", recipients)
        return False


def notify_teacher_new_student(student, request=None):
    teacher = student.teacher
    if not teacher:
        return False
    body = (
        f"Hello {teacher.display_name},\n\n"
        "A new student has registered and is waiting for your approval.\n\n"
        f"Name: {student.display_name}\n"
        f"Email: {student.email}\n\n"
        f"Review it here: {_abs(request, 'student_requests')}\n"
    )
    return _send("New student registration awaiting your approval", body, [teacher.email])


def approve_student(student, request=None):
    student.status = student.Status.APPROVED
    student.approved_at = timezone.now()
    student.rejected_at = None
    student.rejection_reason = ""
    student.save(update_fields=["status", "approved_at", "rejected_at", "rejection_reason"])

    body = (
        f"Hello {student.display_name},\n\n"
        f"Good news! {student.teacher.display_name if student.teacher else 'Your teacher'} has APPROVED your registration.\n"
        "You can now log in and solve quizzes:\n\n"
        f"{_abs(request, 'login')}\n\n"
        "Regards,\nQuiz Portal\n"
    )
    # recipient = the email already saved in the student record
    return _send("Your registration has been approved", body, [student.email])


def reject_student(student, reason="", request=None):
    student.status = student.Status.REJECTED
    student.rejected_at = timezone.now()
    student.approved_at = None
    student.rejection_reason = reason.strip()
    student.save(update_fields=["status", "approved_at", "rejected_at", "rejection_reason"])

    body = f"Hello {student.display_name},\n\nSorry, your registration was REJECTED by your teacher.\n"
    if student.rejection_reason:
        body += f"\nReason: {student.rejection_reason}\n"
    body += "\nRegards,\nQuiz Portal\n"
    return _send("Update on your registration", body, [student.email])
