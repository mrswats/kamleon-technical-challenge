FROM python:3.14-slim-trixie

ENV PATH=/opt/venv/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/_health', timeout=3)"]

WORKDIR /app

COPY requirements.txt .

RUN : && \
    useradd --system --no-create-home app && \
    python -m venv /opt/venv && \
    pip install -r requirements.txt && \
    chown -R app:app /app && \
    :

USER app

COPY . .

CMD ["./entrypoint.sh"]
