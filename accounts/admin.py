from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "status", "teacher", "date_joined")
    list_filter = ("role", "status")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (
        ("Role & approval", {"fields": ("role", "status", "teacher", "approved_at", "rejected_at", "rejection_reason")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + ((None, {"fields": ("email", "role", "status", "teacher")}),)

    def save_model(self, request, obj, form, change):
        # teachers/superusers created here are active immediately
        if not change and (obj.role == User.Role.TEACHER or obj.is_superuser):
            obj.status = User.Status.APPROVED
        super().save_model(request, obj, form, change)
