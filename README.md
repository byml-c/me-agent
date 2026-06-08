# Me.Agent

Graph-native personal agent MVP.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn backend.app.main:app --reload --port 8000
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
