FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAIFE_PROJECT_ROOT=/app \
    CAIFE_REVIEW_DB=/app/review_data/reviews.sqlite3

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir -p /app/review_data
COPY . /app/review_app
EXPOSE 8501
CMD ["streamlit", "run", "review_app/app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]
