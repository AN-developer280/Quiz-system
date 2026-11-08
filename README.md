# Quiz Portal (Django)

Teacher publishes AI-generated quizzes; students register, get approved by their teacher, log in and solve.

## Setup
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # put your ANTHROPIC_API_KEY
python manage.py makemigrations accounts quizzes      # custom user model -> BEFORE migrate
python manage.py migrate
python manage.py createsuperuser                      # only for /django-admin/
python manage.py runserver
```
Emails print in the terminal until EMAIL_HOST* is set in `.env` (Gmail: App Password).

## Flow (PDF workflow: Student = registrant, Teacher = approver)
1. Teacher registers at `/register/teacher/` and logs in directly.
2. Student registers at `/register/student/` and picks a teacher -> record saved with status=PENDING,
   teacher is emailed, student sees "awaiting teacher approval".
3. Teacher opens **Students** (`/teacher/students/`) -> Approve (status=APPROVED, approved_at set, email with login link
   to the saved student.email) or Reject (status=REJECTED + optional reason emailed). Same record is updated, no second record.
4. PENDING/REJECTED students cannot log in (message shown). Approved student -> `/student/`.
5. Teacher: Generate quiz with AI -> draft -> edit questions -> Publish.
6. Student sees only quizzes published by his own teacher, solves once, gets instant result.
7. Teacher sees submissions and each student's answers under Results.
