FROM python:3.14-slim-trixie

ENV PATH=/opt/venv/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies from the hash-pinned lockfile when there is one (see README,
# "Dependency lockfiles"); otherwise resolve them from pyproject.toml.
# `requirements.tx[t]` is optional: the glob may match nothing as long as another
# source in the same COPY exists.
COPY pyproject.toml README.md LICENSE requirements.tx[t] ./
COPY kamleon ./kamleon
RUN python -m venv /opt/venv && \
    if [ -f requirements.txt ]; then \
        pip install --require-hashes -r requirements.txt && pip install --no-deps .; \
    else \
        pip install .; \
    fi

COPY alembic.ini gunicorn.conf.py entrypoint.sh ./
COPY migrations ./migrations

# Do not run as root.
RUN useradd --system --no-create-home app && chmod +x entrypoint.sh
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/_health', timeout=3)"]

CMD ["./entrypoint.sh"]
