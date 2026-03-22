# NeuraForge

NeuraForge is an AI-powered website builder built with Flask. It helps you generate websites from prompts, import existing ZIP projects, edit pages in a browser IDE, and export final builds.

This README is designed for:
- Users who want to run the app and build websites quickly.
- Developers who want to contribute, debug, and extend the platform.

## What You Can Do

- Generate multi-page websites with AI (`/api/generate/`).
- Upload an existing website ZIP and continue editing (`/website/upload`).
- Manage projects from a functional builder dashboard (`/auth/dashboard`).
- Edit pages, sections, and project files in the built-in IDE (`/website/ide/<id>`).
- Preview and export websites as ZIP files.
- Use templates, section components, SEO analysis, and version snapshots.
- Run the optional AI Agent workflow (`/ai-agent/api/run`) with graceful fallback if dependencies are missing.

## Quick Start (Users)

### 1) Prerequisites

- Python `3.10+` (recommended: `3.11`)
- `pip`
- (Optional) Docker Desktop for code execution features

### 2) Install

```bash
git clone https://github.com/your-org/Neuraforge.git
cd Neuraforge
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3) Configure `.env`

Create a `.env` file in project root:

```env
SECRET_KEY=change-me-in-production
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key

# Optional email OTP sender
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_app_password

# Optional Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

Minimum for basic login + dashboard:
- `SECRET_KEY`
- At least one AI key (`GROQ_API_KEY` or `GEMINI_API_KEY`) for generation/chat features

### 4) Run

```bash
python app.py
```

Open:
- `http://127.0.0.1:5000/`

### 5) Typical User Flow

1. Register or log in.
2. Open dashboard (`/auth/dashboard`).
3. Generate a website or upload a ZIP.
4. Open IDE, edit sections/files, preview.
5. Export ZIP.

## Optional Features and Graceful Fallbacks

NeuraForge is hardened so optional integrations do not block app startup.

- Docker SDK missing or Docker engine unavailable:
  - App still starts.
  - Code execution endpoint returns a safe message.
- Google OAuth missing (`Authlib`) or not configured:
  - Email/password auth still works.
  - Google login routes fail gracefully with user-facing feedback.
- AI Agent dependencies missing (for example FAISS):
  - `/ai-agent/api/run` returns controlled `503` with details.
  - Main website builder remains usable.
- OTP email SMTP vars missing:
  - OTP sending falls back to dev-friendly logging behavior.

## Token System (User Plan Logic)

Default roles: `user`, `premium`, `admin`  
Default new user balance: `50` tokens

Action costs (role-aware):
- `generate_website`: user `10`, premium `5`, admin `0`
- `regenerate_section`: user `3`, premium `1`, admin `0`
- `chat_message`: user `1`, premium `0`, admin `0`
- `export_website`: user `2`, premium `0`, admin `0`
- `upload_website`: user `5`, premium `2`, admin `0`

## Developer Guide

### Stack

- Backend: Flask
- ORM: SQLAlchemy + Flask-SQLAlchemy
- DB: SQLite (local default)
- Auth: session-based auth, optional Google OAuth
- AI Providers: Groq and Gemini
- Templates: Jinja2
- Tests: Pytest

### Project Structure

```text
Neuraforge/
  app.py
  core/                  # config, llm clients, email, safe file/command utilities
  modules/
    auth/                # login/register/dashboard/pricing
    ai_generator/        # website generation pipeline
    website/             # IDE, file/page/section CRUD, export/upload/features
    ai_agent/            # optional agent endpoint + dashboard
    chatbot/             # chat APIs
  database/
    models/              # User, Website, Page, Section, ProjectFile, Snapshot, etc.
  templates/             # dashboard, ide, auth pages, preview, pricing
  static/style.css
  tests/
```

### Core Routes

- Auth/UI:
  - `GET/POST /auth/login`
  - `GET/POST /auth/register`
  - `GET /auth/dashboard`
- Generation:
  - `POST /api/generate/`
- Website IDE:
  - `GET /website/ide/<website_id>`
  - `GET /website/view/<website_id>`
- Upload/Export:
  - `POST /website/upload`
  - `GET /website/export/<website_id>`
- File API (canonical):
  - `POST /website/api/file/<website_id>`
  - `PUT /website/api/file/<file_id>`
  - `DELETE /website/api/file/<file_id>`
- File API (legacy compatibility shim):
  - `POST|PUT|DELETE /website/api/website/<website_id>/file`
- Snapshots:
  - `POST /website/api/section/<section_id>/snapshot`
  - `GET /website/api/section/<section_id>/snapshots`
- AI Agent:
  - `GET /ai-agent/`
  - `POST /ai-agent/api/run`

### Local Development Workflow

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
python app.py
```

Run tests:

```bash
pytest -q
```

If you want deterministic offline checks first:

```bash
pytest -q tests/test_agent_security.py
```

### Known Test/Dev Caveats

- `tests/test_agent.py` can fail without working outbound network/LLM access because it exercises AI responses.
- On some Windows setups, pytest cache warnings can occur because of ACL/ownership restrictions.

### Windows ACL and Permission Repair Tips

If you see access errors (pytest cache or repo ownership):

```powershell
git config --global --add safe.directory D:/Open-Source/Neuraforge
```

If cache artifacts are locked by ownership policy, clear or recreate writable cache paths in your user-owned workspace and rerun tests.

### Environment Variables Reference

- `SECRET_KEY`:
  - Flask session secret. Required in production.
- `GROQ_API_KEY`:
  - Enables Groq-powered generation/chat.
- `GEMINI_API_KEY`:
  - Enables Gemini-powered generation/chat.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`:
  - Optional Google OAuth login.
- `MAIL_USERNAME`, `MAIL_PASSWORD`:
  - Optional SMTP sender for OTP emails.

### Production Notes

Before production deployment:

1. Set a strong `SECRET_KEY`.
2. Disable debug mode (`app.run(debug=False)` or use a WSGI server).
3. Replace development auth shortcuts (email auto-verification behavior) with strict verification.
4. Remove hard-coded admin bootstrap logic from auth service.
5. Move from SQLite to a managed database.

## Contributing

1. Create a feature branch.
2. Make focused changes with tests.
3. Run `pytest -q`.
4. Open a pull request with a clear summary and verification steps.

---

If you are new to the project and want a good first task, start by running the app, generating one website from the dashboard, and tracing that flow through:
- `modules/ai_generator/service.py`
- `modules/website/routes.py`
- `templates/dashboard.html`
