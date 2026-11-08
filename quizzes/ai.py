"""AI quiz generation: Google Gemini (free tier) or Anthropic Claude."""
import json
import random
import re

import requests
from django.conf import settings

API_URL = "https://api.anthropic.com/v1/messages"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPTIONS_PER_QUESTION = 4


class AIGenerationError(Exception):
    """Raised with a user-friendly message when generation fails."""


SYSTEM_PROMPT = (
    "You are an expert teacher who writes accurate, unambiguous multiple-choice quizzes. "
    "Every question has exactly 4 options and exactly ONE correct option. "
    "Wrong options must be plausible but clearly wrong. Never use 'all of the above' or 'none of the above'. "
    "Reply with a single JSON object and nothing else (no markdown, no commentary)."
)


def _build_prompt(topic, num_questions, difficulty, instructions, existing):
    prompt = (
        f"Create a quiz.\nTopic: {topic}\nNumber of questions: {num_questions}\n"
        f"Difficulty: {difficulty}\n"
    )
    if instructions:
        prompt += f"Extra instructions from the teacher: {instructions}\n"
    if existing:
        listing = "\n".join(f"- {q}" for q in existing[:60])
        prompt += f"\nDo NOT repeat or rephrase these existing questions:\n{listing}\n"
    prompt += (
        "\nReturn JSON in exactly this shape:\n"
        '{"title": "short quiz title", "questions": [{"question": "...", '
        '"options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "one or two sentences"}]}\n'
        "correct_index is the 0-based index of the correct option."
    )
    return prompt


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise AIGenerationError("The AI returned an unreadable response. Please try again.")


def _normalise(data, wanted):
    raw = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise AIGenerationError("The AI did not return any questions. Please try again.")
    questions = []
    for item in raw:
        try:
            text = str(item["question"]).strip()
            options = [str(o).strip() for o in item["options"]]
            correct = int(item["correct_index"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text or len(options) != OPTIONS_PER_QUESTION or len(set(options)) != OPTIONS_PER_QUESTION:
            continue
        if not 0 <= correct < OPTIONS_PER_QUESTION or not all(options):
            continue
        # shuffle so the right answer is not always in the same position
        pairs = [(o, i == correct) for i, o in enumerate(options)]
        random.shuffle(pairs)
        questions.append(
            {
                "text": text,
                "explanation": str(item.get("explanation", "")).strip(),
                "choices": [{"text": o, "is_correct": ok} for o, ok in pairs],
            }
        )
    if not questions:
        raise AIGenerationError("The AI returned invalid questions. Please try again.")
    return questions[:wanted]


def _post(url, headers, payload):
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=settings.AI_REQUEST_TIMEOUT)
    except requests.RequestException:
        raise AIGenerationError("Could not reach the AI service. Check the internet connection and try again.")
    if resp.status_code in (400, 401, 403):
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise AIGenerationError(f"The AI service rejected the request ({resp.status_code}). Check the API key / model name. {detail}"[:300])
    if resp.status_code == 404:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise AIGenerationError(f"AI model not found (404). Model in use: '{getattr(settings, 'GEMINI_MODEL', '')}'. {detail}"[:350])
    if resp.status_code == 429:
        raise AIGenerationError("The AI free limit was reached. Please wait a minute and try again.")
    if resp.status_code >= 400:
        raise AIGenerationError(f"The AI service returned an error ({resp.status_code}). Please try again.")
    try:
        return resp.json()
    except ValueError:
        raise AIGenerationError("Unexpected response from the AI service.")


def _call_gemini(prompt):
    url = GEMINI_URL.format(model=settings.GEMINI_MODEL)
    headers = {"x-goog-api-key": settings.GEMINI_API_KEY, "content-type": "application/json"}
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }
    body = _post(url, headers, payload)
    try:
        return "".join(p.get("text", "") for p in body["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError):
        raise AIGenerationError("The AI returned no answer (it may have been blocked). Try a different topic.")


def _call_anthropic(prompt):
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": 8000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    body = _post(API_URL, headers, payload)
    try:
        return "".join(b.get("text", "") for b in body["content"] if b.get("type") == "text")
    except (KeyError, TypeError):
        raise AIGenerationError("Unexpected response from the AI service.")


def generate_quiz(topic, num_questions, difficulty="medium", instructions="", existing_questions=None):
    """Return {'title': str, 'questions': [{'text', 'explanation', 'choices': [...]}]}."""
    prompt = _build_prompt(topic, num_questions, difficulty, instructions, existing_questions)
    if settings.GEMINI_API_KEY:
        text = _call_gemini(prompt)
    elif settings.ANTHROPIC_API_KEY:
        text = _call_anthropic(prompt)
    else:
        raise AIGenerationError("AI is not configured. Set GEMINI_API_KEY in the .env file (free key from aistudio.google.com).")

    data = _extract_json(text)
    return {
        "title": str(data.get("title", "")).strip() if isinstance(data, dict) else "",
        "questions": _normalise(data, num_questions),
    }
