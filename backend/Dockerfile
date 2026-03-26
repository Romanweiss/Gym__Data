FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
COPY backend/tests ./backend/tests
COPY ingestion/pyproject.toml ./ingestion/pyproject.toml
COPY ingestion/gym_data_ingestion ./ingestion/gym_data_ingestion

RUN pip install --upgrade pip && pip install "./ingestion" "./backend[test]"

WORKDIR /srv/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
