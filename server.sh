set -a
source .env
set +a

.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000