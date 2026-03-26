FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/ingestion

COPY pyproject.toml ./
COPY gym_data_ingestion ./gym_data_ingestion
COPY tests ./tests

RUN pip install --upgrade pip && pip install ".[test]"

CMD ["python", "-m", "gym_data_ingestion.cli.main", "load-all"]
