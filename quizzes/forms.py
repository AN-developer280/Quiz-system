from django import forms

from .models import Choice, Quiz


class GenerateQuizForm(forms.Form):
    topic = forms.CharField(max_length=255, label="Topic", help_text="e.g. Photosynthesis, Python loops, Pakistan history")
    title = forms.CharField(max_length=200, required=False, help_text="Optional - AI will suggest a title")
    num_questions = forms.IntegerField(min_value=1, max_value=25, initial=10, label="Number of questions")
    difficulty = forms.ChoiceField(choices=Quiz.Difficulty.choices, initial=Quiz.Difficulty.MEDIUM)
    time_limit_minutes = forms.IntegerField(
        min_value=1, max_value=300, required=False, label="Time limit (minutes)", help_text="Leave empty for no limit"
    )
    instructions = forms.CharField(
        required=False,
        label="Extra instructions",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "e.g. Class 9 level, focus on chapter 3, include numerical problems"}),
    )


class AddQuestionsForm(forms.Form):
    num_questions = forms.IntegerField(min_value=1, max_value=15, initial=5, label="How many more?")
    instructions = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Optional focus"}))


class QuizEditForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ("title", "description", "difficulty", "time_limit_minutes")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class QuestionForm(forms.Form):
    text = forms.CharField(label="Question", widget=forms.Textarea(attrs={"rows": 3}))
    option_1 = forms.CharField(max_length=500)
    option_2 = forms.CharField(max_length=500)
    option_3 = forms.CharField(max_length=500)
    option_4 = forms.CharField(max_length=500)
    correct = forms.ChoiceField(
        choices=[("1", "Option 1"), ("2", "Option 2"), ("3", "Option 3"), ("4", "Option 4")],
        label="Correct option",
        widget=forms.RadioSelect,
    )
    explanation = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    @classmethod
    def from_question(cls, question):
        choices = list(question.choices.all())
        initial = {"text": question.text, "explanation": question.explanation}
        for i, c in enumerate(choices[:4], start=1):
            initial[f"option_{i}"] = c.text
            if c.is_correct:
                initial["correct"] = str(i)
        return cls(initial=initial)

    def clean(self):
        data = super().clean()
        options = [(data.get(f"option_{i}") or "").strip().lower() for i in range(1, 5)]
        if all(options) and len(set(options)) != 4:
            raise forms.ValidationError("All four options must be different.")
        return data

    def save_to(self, question):
        """Write cleaned data into a saved Question (replaces its choices)."""
        d = self.cleaned_data
        question.text = d["text"].strip()
        question.explanation = d["explanation"].strip()
        question.save()
        question.choices.all().delete()
        for i in range(1, 5):
            Choice.objects.create(
                question=question,
                text=d[f"option_{i}"].strip(),
                is_correct=(d["correct"] == str(i)),
                order=i,
            )
        return question
