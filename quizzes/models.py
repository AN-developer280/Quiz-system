from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Quiz(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Leave empty for no time limit")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "quizzes"

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    def has_attempts(self):
        return self.attempts.exists()


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]

    @property
    def correct_choice(self):
        return next((c for c in self.choices.all() if c.is_correct), None)


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class Attempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["quiz", "student"], name="one_attempt_per_student_per_quiz"),
        ]

    def __str__(self):
        return f"{self.student} - {self.quiz} ({self.score}/{self.total})"

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    @property
    def percentage(self):
        return round(self.score * 100 / self.total) if self.total else 0

    def deadline(self):
        if not self.quiz.time_limit_minutes:
            return None
        return self.started_at + timedelta(minutes=self.quiz.time_limit_minutes)

    def remaining_seconds(self):
        d = self.deadline()
        if d is None:
            return None
        return max(0, int((d - timezone.now()).total_seconds()))

    def is_overdue(self, grace_seconds=60):
        d = self.deadline()
        return d is not None and timezone.now() > d + timedelta(seconds=grace_seconds)


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    selected_choice = models.ForeignKey(Choice, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="one_answer_per_question"),
        ]
