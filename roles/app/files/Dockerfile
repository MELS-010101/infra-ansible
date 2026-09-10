# Ansible managed
FROM python:3.12-alpine
RUN pip install --no-cache-dir opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
WORKDIR /app
COPY app.py /app/app.py
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ || exit 1
CMD ["python3", "/app/app.py"]
