# This Dockerfile is intended solely for local development of Misago
# If you are seeking a suitable Docker setup for running Misago in a 
# production, please use misago-docker instead
FROM registry.cn-hangzhou.aliyuncs.com/library/python:3.12-bookworm

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV IN_MISAGO_DOCKER 1
ENV MISAGO_PLUGINS "/app/plugins"

# Use China mainland mirror for apt
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# Install env dependencies in one single command/layer
RUN apt-get update && apt-get install -y --allow-unauthenticated \
    vim \
    libffi-dev \
    libssl-dev \
    sqlite3 \
    libjpeg-dev \
    libopenjp2-7-dev \
    locales \
    cron \
    postgresql-client-15 \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Add files and dirs for build step
COPY dev /app/dev
COPY plugins /app/plugins
COPY requirements.txt /app/requirements.txt

WORKDIR /app/

# Use China mainland mirror for pip
ENV PIP_INDEX_URL https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST mirrors.aliyun.com

# Install Misago requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir pip-tools

# Bootstrap plugins
RUN ./dev bootstrap_plugins

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
