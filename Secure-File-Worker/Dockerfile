FROM python:3.11-slim
RUN useradd --system --uid 10001 --no-create-home worker
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV INPUT_DIR=/data/input
RUN mkdir -p /data/input
USER 10001
EXPOSE 5000
CMD ["python", "-m", "flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5000"]