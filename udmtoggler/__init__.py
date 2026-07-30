# Ensure celery app is always imported with Django
from .celery import app as celery_app
