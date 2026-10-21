FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Collect with build-only settings: no database or production secrets needed.
RUN DJANGO_SETTINGS_MODULE=config.build python manage.py collectstatic --noinput
ENV DJANGO_SETTINGS_MODULE=config.production
EXPOSE 8000
CMD ["python", "deploy/start.py"]
