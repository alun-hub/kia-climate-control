# k3s deployment image (amd64). Based on the repo's ../Dockerfile with two additions:
#  - tzdata + TZ so the scheduler thread uses Europe/Stockholm local time
#  - /app/.env symlinked onto the data volume so admin-page credentials persist
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc \
      tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    TZ=Europe/Stockholm \
    PORT=5000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kia_backend.py .
COPY public/ ./public/

# schedules.json lives in /app/data (a PVC). Point /app/.env at the same volume
# so credentials saved via the admin page survive pod restarts.
RUN mkdir -p /app/data && ln -sf /app/data/.env /app/.env

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"

CMD ["python", "kia_backend.py"]
