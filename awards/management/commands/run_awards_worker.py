"""Management command to run the awards evaluation worker.

Polls the `awards_eval_pending` Redis set for callsign IDs that need
award re-evaluation, then processes them in batches.
"""

import signal
import time

import redis
from django.conf import settings
from django.core.management.base import BaseCommand

from awards.worker import process_pending_batch

BATCH_SIZE = 50
POLL_INTERVAL = 2  # seconds to sleep when queue is empty


class Command(BaseCommand):
    help = "Run the awards evaluation worker (polls Redis for pending callsign IDs)"

    def handle(self, *args, **options):
        r = redis.from_url(settings.REDIS_URL)
        self.stdout.write("Awards worker started, polling awards_eval_pending ...")

        running = True

        def shutdown(signum, frame):
            nonlocal running
            self.stdout.write("Shutting down ...")
            running = False

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        while running:
            # SPOP returns a set of members (bytes)
            raw = r.spop("awards_eval_pending", BATCH_SIZE)
            if not raw:
                time.sleep(POLL_INTERVAL)
                continue

            callsign_ids = []
            for item in raw:
                try:
                    callsign_ids.append(int(item))
                except ValueError, TypeError:
                    self.stderr.write(f"Invalid callsign ID in queue: {item!r}")

            if callsign_ids:
                self.stdout.write(f"Processing {len(callsign_ids)} callsign IDs")
                try:
                    process_pending_batch(callsign_ids)
                except Exception:
                    # SPOP already removed the batch; put it back so a
                    # transient failure (DB down, etc.) doesn't lose the
                    # evaluations. Re-evaluation is idempotent.
                    self.stderr.write("Batch failed; requeueing")
                    r.sadd("awards_eval_pending", *callsign_ids)
                    time.sleep(POLL_INTERVAL)

        self.stdout.write("Awards worker stopped.")
