from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class _BaseRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class TeacherRegistrationForm(_BaseRegistrationForm):
    """Teachers can log in immediately after registering."""

    def save(self, commit=True):
        user = super().save(commit=False)  # password is hashed by UserCreationForm
        user.role = User.Role.TEACHER
        user.status = User.Status.APPROVED
        if commit:
            user.save()
        return user


class TeacherChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


class StudentRegistrationForm(_BaseRegistrationForm):
    """Saved immediately with status=PENDING; the chosen teacher decides."""

    teacher = TeacherChoiceField(
        queryset=User.objects.none(),
        label="Your teacher",
        empty_label="-- select your teacher --",
        help_text="This teacher will approve your registration and publish your quizzes.",
    )

    class Meta(_BaseRegistrationForm.Meta):
        fields = ("first_name", "last_name", "username", "email", "teacher")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = User.objects.filter(
            role=User.Role.TEACHER, status=User.Status.APPROVED, is_active=True
        ).order_by("first_name", "username")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.status = User.Status.PENDING  # awaiting teacher decision
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Blocks PENDING / REJECTED students with a clear message."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_student:
            return
        if user.is_pending:
            raise forms.ValidationError(
                "Your registration is still awaiting your teacher's approval. "
                "You will receive an email as soon as a decision is made.",
                code="pending",
            )
        if user.is_rejected:
            msg = "Your registration was rejected by your teacher."
            if user.rejection_reason:
                msg += f" Reason: {user.rejection_reason}"
            raise forms.ValidationError(msg, code="rejected")


class RejectForm(forms.Form):
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Reason (optional) - included in the email"}),
    )
