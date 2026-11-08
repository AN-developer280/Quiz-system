from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import student_required, teacher_required
from accounts.models import User

from . import ai
from .forms import AddQuestionsForm, GenerateQuizForm, QuestionForm, QuizEditForm
from .models import Answer, Attempt, Choice, Question, Quiz


# ================================================================ helpers
def _own_quiz(request, pk):
    return get_object_or_404(Quiz, pk=pk, teacher=request.user)


def _save_ai_questions(quiz, items):
    start = (quiz.questions.order_by("-order").values_list("order", flat=True).first() or 0) + 1
    for offset, item in enumerate(items):
        q = Question.objects.create(quiz=quiz, text=item["text"], explanation=item["explanation"], order=start + offset)
        Choice.objects.bulk_create(
            [Choice(question=q, text=c["text"], is_correct=c["is_correct"], order=i) for i, c in enumerate(item["choices"], 1)]
        )


def _locked(request, quiz):
    """Questions can't change once students have attempted (it would alter graded results)."""
    if quiz.has_attempts():
        messages.error(request, "Students have already attempted this quiz, so its questions can no longer be changed.")
        return True
    return False


def _review_rows(attempt):
    answers = {a.question_id: a.selected_choice_id for a in attempt.answers.all()}
    rows = []
    for q in attempt.quiz.questions.prefetch_related("choices"):
        selected_id = answers.get(q.id)
        choices = list(q.choices.all())
        rows.append(
            {
                "question": q,
                "choices": choices,
                "selected_id": selected_id,
                "correct": any(c.id == selected_id and c.is_correct for c in choices),
            }
        )
    return rows


# ================================================================ teacher
@teacher_required
def teacher_dashboard(request):
    quizzes = Quiz.objects.filter(teacher=request.user).annotate(
        q_count=Count("questions", distinct=True),
        a_count=Count("attempts", filter=Q(attempts__submitted_at__isnull=False), distinct=True),
    )
    return render(
        request,
        "teacher/dashboard.html",
        {
            "quizzes": quizzes,
            "published_count": sum(1 for q in quizzes if q.is_published),
            "draft_count": sum(1 for q in quizzes if not q.is_published),
            "attempt_total": sum(q.a_count for q in quizzes),
            "pending_students": User.objects.filter(
                role=User.Role.STUDENT, teacher=request.user, status=User.Status.PENDING
            ).count(),
        },
    )


@teacher_required
def quiz_generate(request):
    form = GenerateQuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            result = ai.generate_quiz(d["topic"], d["num_questions"], d["difficulty"], d["instructions"])
        except ai.AIGenerationError as exc:
            messages.error(request, str(exc))
        else:
            with transaction.atomic():
                quiz = Quiz.objects.create(
                    teacher=request.user,
                    title=d["title"] or result["title"] or d["topic"],
                    topic=d["topic"],
                    difficulty=d["difficulty"],
                    time_limit_minutes=d["time_limit_minutes"],
                )
                _save_ai_questions(quiz, result["questions"])
            messages.success(request, "Quiz generated as a DRAFT. Review the questions, then publish it for students.")
            return redirect("quizzes:quiz_detail", pk=quiz.pk)
    return render(request, "teacher/quiz_generate.html", {"form": form})


@teacher_required
def quiz_detail(request, pk):
    quiz = _own_quiz(request, pk)
    return render(
        request,
        "teacher/quiz_detail.html",
        {
            "quiz": quiz,
            "questions": quiz.questions.prefetch_related("choices"),
            "add_form": AddQuestionsForm(),
            "locked": quiz.has_attempts(),
            "attempt_count": quiz.attempts.filter(submitted_at__isnull=False).count(),
        },
    )


@teacher_required
def quiz_edit(request, pk):
    quiz = _own_quiz(request, pk)
    form = QuizEditForm(request.POST or None, instance=quiz)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Quiz details updated.")
        return redirect("quizzes:quiz_detail", pk=quiz.pk)
    return render(request, "teacher/quiz_edit.html", {"quiz": quiz, "form": form})


@teacher_required
@require_POST
def quiz_publish(request, pk):
    quiz = _own_quiz(request, pk)
    if not quiz.questions.exists():
        messages.error(request, "Add at least one question before publishing.")
    else:
        quiz.status = Quiz.Status.PUBLISHED
        quiz.published_at = timezone.now()
        quiz.save(update_fields=["status", "published_at"])
        messages.success(request, "Quiz published. Logged-in students can now see and solve it.")
    return redirect("quizzes:quiz_detail", pk=quiz.pk)


@teacher_required
@require_POST
def quiz_unpublish(request, pk):
    quiz = _own_quiz(request, pk)
    quiz.status = Quiz.Status.DRAFT
    quiz.save(update_fields=["status"])
    messages.info(request, "Quiz moved back to draft. Students can no longer start it.")
    return redirect("quizzes:quiz_detail", pk=quiz.pk)


@teacher_required
def quiz_delete(request, pk):
    quiz = _own_quiz(request, pk)
    if request.method == "POST":
        quiz.delete()
        messages.success(request, "Quiz deleted.")
        return redirect("quizzes:teacher_dashboard")
    return render(
        request,
        "teacher/confirm_delete.html",
        {"quiz": quiz, "attempt_count": quiz.attempts.count()},
    )


@teacher_required
@require_POST
def quiz_add_ai_questions(request, pk):
    quiz = _own_quiz(request, pk)
    if _locked(request, quiz):
        return redirect("quizzes:quiz_detail", pk=quiz.pk)
    form = AddQuestionsForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid number of questions (1-15).")
        return redirect("quizzes:quiz_detail", pk=quiz.pk)
    d = form.cleaned_data
    try:
        result = ai.generate_quiz(
            quiz.topic, d["num_questions"], quiz.difficulty, d["instructions"],
            existing_questions=list(quiz.questions.values_list("text", flat=True)),
        )
    except ai.AIGenerationError as exc:
        messages.error(request, str(exc))
    else:
        with transaction.atomic():
            _save_ai_questions(quiz, result["questions"])
        messages.success(request, f"{len(result['questions'])} question(s) added.")
    return redirect("quizzes:quiz_detail", pk=quiz.pk)


@teacher_required
def question_add(request, pk):
    quiz = _own_quiz(request, pk)
    if _locked(request, quiz):
        return redirect("quizzes:quiz_detail", pk=quiz.pk)
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        nxt = (quiz.questions.order_by("-order").values_list("order", flat=True).first() or 0) + 1
        with transaction.atomic():
            form.save_to(Question(quiz=quiz, order=nxt))
        messages.success(request, "Question added.")
        return redirect("quizzes:quiz_detail", pk=quiz.pk)
    return render(request, "teacher/question_form.html", {"quiz": quiz, "form": form, "title": "Add question"})


@teacher_required
def question_edit(request, pk, qpk):
    quiz = _own_quiz(request, pk)
    question = get_object_or_404(Question, pk=qpk, quiz=quiz)
    if _locked(request, quiz):
        return redirect("quizzes:quiz_detail", pk=quiz.pk)
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save_to(question)
            messages.success(request, "Question updated.")
            return redirect("quizzes:quiz_detail", pk=quiz.pk)
    else:
        form = QuestionForm.from_question(question)
    return render(request, "teacher/question_form.html", {"quiz": quiz, "form": form, "title": "Edit question"})


@teacher_required
@require_POST
def question_delete(request, pk, qpk):
    quiz = _own_quiz(request, pk)
    question = get_object_or_404(Question, pk=qpk, quiz=quiz)
    if not _locked(request, quiz):
        question.delete()
        messages.success(request, "Question deleted.")
    return redirect("quizzes:quiz_detail", pk=quiz.pk)


@teacher_required
def quiz_results(request, pk):
    quiz = _own_quiz(request, pk)
    attempts = quiz.attempts.filter(submitted_at__isnull=False).select_related("student").order_by("-score", "submitted_at")
    count = attempts.count()
    avg = round(sum(a.percentage for a in attempts) / count) if count else 0
    return render(request, "teacher/quiz_results.html", {"quiz": quiz, "attempts": attempts, "avg": avg, "count": count})


@teacher_required
def teacher_attempt_detail(request, pk):
    attempt = get_object_or_404(
        Attempt.objects.select_related("quiz", "student"), pk=pk, quiz__teacher=request.user, submitted_at__isnull=False
    )
    return render(
        request,
        "student/result.html",
        {
            "attempt": attempt,
            "rows": _review_rows(attempt),
            "back_link": reverse("quizzes:quiz_results", args=[attempt.quiz_id]),
            "teacher_view": True,
        },
    )


# ================================================================ student
@student_required
def student_dashboard(request):
    mine = {a.quiz_id: a for a in Attempt.objects.filter(student=request.user)}
    published = Quiz.objects.filter(status=Quiz.Status.PUBLISHED, teacher_id=request.user.teacher_id).select_related("teacher").annotate(q_count=Count("questions"))
    available, done = [], []
    for quiz in published:
        attempt = mine.get(quiz.id)
        quiz.attempt = attempt
        (done if attempt and attempt.is_submitted else available).append(quiz)
    history = Attempt.objects.filter(student=request.user, submitted_at__isnull=False).select_related("quiz").order_by("-submitted_at")
    return render(request, "student/dashboard.html", {"available": available, "history": history, "done_count": len(done)})


@student_required
def quiz_take(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, status=Quiz.Status.PUBLISHED, teacher_id=request.user.teacher_id)
    questions = list(quiz.questions.prefetch_related("choices"))
    if not questions:
        messages.error(request, "This quiz has no questions yet.")
        return redirect("quizzes:student_dashboard")

    attempt, _ = Attempt.objects.get_or_create(quiz=quiz, student=request.user)
    if attempt.is_submitted:
        messages.info(request, "You have already completed this quiz.")
        return redirect("quizzes:student_result", pk=attempt.pk)

    if request.method == "POST":
        overdue = attempt.is_overdue()
        with transaction.atomic():
            locked = Attempt.objects.select_for_update().get(pk=attempt.pk)
            if locked.is_submitted:
                return redirect("quizzes:student_result", pk=attempt.pk)
            score = 0
            for q in questions:
                choice = None
                raw = "" if overdue else request.POST.get(f"q_{q.pk}", "")
                if raw.isdigit():
                    choice = next((c for c in q.choices.all() if c.pk == int(raw)), None)
                Answer.objects.create(attempt=locked, question=q, selected_choice=choice)
                if choice and choice.is_correct:
                    score += 1
            locked.score = score
            locked.total = len(questions)
            locked.submitted_at = timezone.now()
            locked.save()
        if overdue:
            messages.error(request, "Time was over before submission, so late answers were not counted.")
        return redirect("quizzes:student_result", pk=attempt.pk)

    return render(
        request,
        "student/quiz_take.html",
        {"quiz": quiz, "questions": questions, "attempt": attempt, "remaining": attempt.remaining_seconds()},
    )


@student_required
def student_result(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("quiz"), pk=pk, student=request.user, submitted_at__isnull=False)
    return render(
        request,
        "student/result.html",
        {"attempt": attempt, "rows": _review_rows(attempt), "back_link": reverse("quizzes:student_dashboard")},
    )
