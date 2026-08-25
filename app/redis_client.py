"""Shared Redis client.

One client (and its connection pool) per process; connections are created
lazily on first use, so importing this at startup is free.
"""

import redis
from django.conf import settings

client = redis.from_url(settings.REDIS_URL)
