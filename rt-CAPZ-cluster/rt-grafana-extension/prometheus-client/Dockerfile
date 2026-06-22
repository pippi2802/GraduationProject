# rt-DRA NodeAllocationState Prometheus exporter
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXPORTER_PORT=9101

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py .

# Run as an unprivileged user.
RUN useradd -u 10001 -r -s /usr/sbin/nologin exporter
USER 10001

EXPOSE 9101

ENTRYPOINT ["python", "exporter.py"]
