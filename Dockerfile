FROM python:3.13-slim

LABEL Name=UDM-Toggler Version=1.2

WORKDIR /app
ADD . /app

RUN python3 -m pip install --upgrade pip

# Install pipenv and supervisor
RUN python3 -m pip install pipenv supervisor
RUN pipenv sync --system

# Copy supervisord config
COPY supervisord.conf /app/supervisord.conf

# Use supervisord to run both gunicorn and celery
CMD ["supervisord", "-c", "/app/supervisord.conf"]
