FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAIFE_PROJECT_ROOT=/app \
    CAIFE_REVIEW_DB=/app/review_data/reviews.sqlite3

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /app/review_app
EXPOSE 8501
CMD ["uvicorn", "app:app", "--app-dir", "/app/review_app", "--host", "0.0.0.0", "--port", "8501"]
