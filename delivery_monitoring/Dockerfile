FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir prometheus-client
COPY delivery_metrics.py .
CMD ["python", "-u", "delivery_metrics.py"]
