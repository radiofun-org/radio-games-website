FROM python:3.14-slim-trixie AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH=/venv/bin:$PATH \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/venv \
    PAGER=cat

# Install system-level dependencies and packages.
RUN apt-get update \
 && apt-get install --assume-yes --no-install-recommends \
    curl \
    gettext \
    libffi8 \
    libjpeg62-turbo \
    libmagic-dev \
    libpcre2-8-0 \
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

# cffi (via cryptography) needs libffi-dev + gcc to build on aarch64/3.14.
RUN apt-get update \
 && apt-get install --assume-yes --no-install-recommends \
    build-essential \
    libffi-dev \
 && uv venv /venv --allow-existing \
 && uv sync --frozen \
 && apt-get remove --assume-yes build-essential libffi-dev \
 && apt-get autoremove --assume-yes \
 && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

COPY . /app/

# Mark port 7373 as being exposed (useful for orchestration).
EXPOSE 7373

CMD ["./serve.sh"]
