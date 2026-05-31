FROM python:3.12.0-slim

ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && awk '!/^torch$/ && !/^--extra-index-url/ {print}' requirements.txt > /tmp/requirements_rest.txt \
    && pip install --no-cache-dir -r /tmp/requirements_rest.txt \
    && rm -f /tmp/requirements_rest.txt

COPY . .

ENV PYTHONPATH=/app
ENV UVICORN_WORKERS=4

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}"]
