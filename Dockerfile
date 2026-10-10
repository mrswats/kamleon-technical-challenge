FROM python:3.14-slim-trixie

ENV PATH=/opt/venv/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt

COPY requirements.txt .

RUN : & \
    apt-get update && \
    apt-get install --assume-yes \
        postgresql \
        && \
    python -m venv venv && \
    python -m pip install -r requirements.txt && \
    :

COPY . .

CMD ["./entrypoint.sh"]
