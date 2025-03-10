FROM python:3.12-slim-bullseye AS base

ENV PATH=$PATH:/root/.local/bin \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=false \
    PIP_DISABLE_PIP_VERSION_CHECK=false \
    PAGER=cat

# Install system-level dependencies and packages.
RUN apt-get update \
 && apt-get install --assume-yes --no-install-recommends \
    curl \
    gettext \
    libffi7 \
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

COPY requirements.txt /app/

# Install our application requirements and build constraints.txt file required by plugins.
RUN apt-get autoremove \
 && apt-get update \
 && apt-get install --assume-yes --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
 && pip install -r requirements.txt \
 && apt-get remove --assume-yes \
    build-essential \
    libffi-dev \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/* \
 && rm -rf /root/.cache \
 && apt-get autoremove --assume-yes \
 && apt-get clean --assume-yes \
 && rm -rf /tmp/*

COPY . /app/

# Mark port 8000 as being exposed (useful for orchestration).
EXPOSE 8000

CMD ["/bin/bash", "serve.sh"]
