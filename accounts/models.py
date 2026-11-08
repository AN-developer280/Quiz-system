from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """One user table for the two modules: Teacher and Student.

    Teacher: registers and can log in immediately.
    Student: registers with status=PENDING and chooses a teacher. That teacher
    approves/rejects the SAME record (status update only, no second record).
    """

    class Role(models.TextChoices):
        TEACHER = "teacher", "Teacher"
        STUDENT = "student", "Student"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    # Students only: the teacher who reviews and teaches this student
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
        limit_choices_to={"role": "teacher"},
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED
