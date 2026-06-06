FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN addgroup --system app && adduser --system --ingroup app app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os, urllib.request; port=os.getenv('PORT', os.getenv('APP_PORT', '8080')); key=os.getenv('HEALTHCHECK_API_KEY', os.getenv('VIEWER_API_KEY', 'dev-viewer-key')); req=urllib.request.Request(f'http://127.0.0.1:{port}/health', headers={'X-API-Key': key}); urllib.request.urlopen(req, timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-${APP_PORT:-8080}}"]
