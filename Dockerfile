FROM python:3.14-slim-bookworm AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    UV_COMPILE_BYTECODE=1 \
    PAGER=cat

# Install system-level dependencies and packages.
RUN apt-get update \
 && apt-get install --assume-yes --no-install-recommends \
    curl \
    gettext \
    libffi8 \
    libjpeg62-turbo \
    libmagic-dev \
    libpcre3 \
    libtool \
    libxml2 \
    libxslt1.1 \
    xmlsec1 \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get autoremove --assume-yes \
 && apt-get clean --assume-yes \
 && rm -rf /tmp/*

WORKDIR /app

# Install a few basic utilities for debugging.
RUN apt-get update \
 && apt-get install --assume-yes --no-install-recommends \
    git \
    less \
    postgresql-client \
    procps \
    vim \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get autoremove --assume-yes \
 && apt-get clean --assume-yes \
 && rm -rf /tmp/*

# Generate the /etc/ssl/certs/ca-certificates.crt
RUN update-ca-certificates --fresh --verbose

COPY pyproject.toml uv.lock /app/
COPY infrastructure/uv.toml /root/.config/uv/uv.toml

# Install dependencies (psycopg[binary] provides pre-built wheels, no build deps needed).
RUN uv sync --frozen \
 && rm -rf /root/.cache

COPY . /app/

# Mark port 8000 as being exposed (useful for orchestration).
EXPOSE 8000

CMD ["./serve.sh"]
