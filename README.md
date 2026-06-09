# Me.Agent

Graph-native personal agent MVP.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn backend.app.main:app --reload --port 8000
```

CLI:

```bash
me-agent chat "记录一个 todo：完善后端 CLI" --no-proposals
me-agent nodes list --json
me-agent proposals list --json
```

Tests:

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The backend reads OpenAI-compatible settings from `.env`:

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_BASE_MODEL
```
