# NeuraForge

NeuraForge is an AI-powered website builder with:
- auth + dashboard
- AI website generation
- in-browser IDE and preview
- project upload/export
- optional AI coding agent

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Create `.env` (example):
```env
SECRET_KEY=change-me
GROQ_API_KEY=
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MAIL_USERNAME=
MAIL_PASSWORD=
```
4. Run:
```bash
python app.py
```

Open `http://127.0.0.1:5000`.

## Runtime Notes

- `Authlib` (Google OAuth) is optional at runtime.  
  If missing or unconfigured, email/password auth still works.
- Docker-backed code execution is optional.  
  If Docker is unavailable, the app still boots and returns a clear error for execution requests.
- AI agent dependencies (`faiss-cpu`, `sentence-transformers`) are optional.  
  Missing dependencies return a controlled `503` response from `/ai-agent/api/run`.

## Recommended Python Version

- Recommended: **Python 3.11 or 3.12**
- Python 3.13 may not support all optional AI-agent dependencies (notably FAISS wheels).

## Windows Environment Repair

If you hit ownership/permission issues:

1. Mark repository as safe for git:
```bash
git config --global --add safe.directory D:/Open-Source/Neuraforge
```
2. Remove stale pytest temp directories:
```powershell
Get-ChildItem -Force . | Where-Object { $_.Name -like 'pytest-cache-files-*' } | Remove-Item -Recurse -Force
```
3. Ensure `instance/neuraforge.db` is writable by your current user.

## Tests and Checks

Run tests:
```bash
pytest
```

Quick parse check for Python files:
```bash
python -m compileall -q .
```
