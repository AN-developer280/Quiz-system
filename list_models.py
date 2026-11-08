"""Prints the Gemini models your key can use. Run: python list_models.py
Reads GEMINI_API_KEY from .env (the key is never printed)."""
import pathlib

import requests

key = ""
for line in (pathlib.Path(__file__).parent / ".env").read_text(encoding="utf-8").splitlines():
    if line.strip().startswith("GEMINI_API_KEY="):
        key = line.split("=", 1)[1].strip().strip('"').strip("'")

if not key:
    raise SystemExit("GEMINI_API_KEY is empty in .env")

r = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": key},
    params={"pageSize": 200},
    timeout=30,
)
print("HTTP status:", r.status_code)
if r.status_code != 200:
    print(r.text[:400])
    raise SystemExit(1)

print("\nModels you can put in GEMINI_MODEL:\n")
for m in r.json().get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(m["name"].replace("models/", ""))
