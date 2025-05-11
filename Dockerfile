FROM python:3.12-slim

LABEL Name=UDM-Toggler Version=1.2

WORKDIR /app
ADD . /app

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install pipenv
RUN pipenv sync --system

CMD ["gunicorn", "udmtoggler.wsgi:application", "--bind", "0.0.0.0:8000"]
