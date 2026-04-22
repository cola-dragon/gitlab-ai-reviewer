FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY prompts ./prompts
COPY docker/docker-start.sh ./docker/docker-start.sh

RUN chmod +x ./docker/docker-start.sh

EXPOSE 8000

CMD ["./docker/docker-start.sh"]
