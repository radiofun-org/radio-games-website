"""Populate the database with realistic dev data for beau@beaugunderson.com."""

import random
import time

from django.core.management.base import BaseCommand

from app.models import AuthUser, CallsignAssociation, LogUpload
from contacts.decode import EPOCH
from contacts.models import AdifMetadata, Callsign, Contact, Match


def encode_grid(locator: str) -> tuple[int, int]:
    """Encode a Maidenhead grid to (number, length). Matches Go maidenheadToNumber."""
    if not locator:
        return 0, 0
    loc = locator.upper()
    n = (ord(loc[0]) - 65) * 18 + (ord(loc[1]) - 65)
    if len(loc) >= 4:
        n = n * 100 + (ord(loc[2]) - 48) * 10 + (ord(loc[3]) - 48)
    if len(loc) >= 6:
        n = n * 576 + (ord(loc[4]) - 65) * 24 + (ord(loc[5]) - 65)
    if len(loc) >= 8:
        n = n * 100 + (ord(loc[6]) - 48) * 10 + (ord(loc[7]) - 48)
    return n + 1, len(locator)

# Band/mode integer codes (must match Go matcher's adif.go)
BAND_20M = 8
BAND_40M = 6
BAND_15M = 10
BAND_10M = 12
BAND_80M = 4
BAND_2M = 17
BAND_70CM = 19

MODE_FT8 = 29
MODE_FT4 = 28
MODE_SSB = 90
MODE_CW = 14

SUB_USB = 172
SUB_LSB = 76
SUB_FT4 = 37

# Common US/DX callsigns with DXCC entity code, CQ zone, ITU zone, grid
OTHER_STATIONS = [
    ("W1AW", 291, 5, 8, "FN31pr"),
    ("K3LR", 291, 5, 8, "EN91jk"),
    ("W3LPL", 291, 5, 8, "FM19la"),
    ("N1MM", 291, 5, 8, "FN31kq"),
    ("K1TTT", 291, 5, 8, "FN32ll"),
    ("W6RJ", 291, 3, 6, "CM87wj"),
    ("K6XX", 291, 3, 6, "CM97ai"),
    ("N6MJ", 291, 3, 6, "DM04wd"),
    ("VE3EJ", 1, 4, 4, "FN03bi"),
    ("VE7CC", 1, 3, 2, "CN89lg"),
    ("G3PQA", 223, 14, 27, "IO91wl"),
    ("DL1IAO", 230, 14, 28, "JO62pk"),
    ("JA1NUT", 339, 25, 45, "PM95vq"),
    ("ZL1BYZ", 170, 32, 60, "RF73dc"),
    ("PY2EX", 108, 11, 15, "GG66ok"),
    ("LU1FAM", 100, 13, 14, "GF05tj"),
    ("VK3MO", 150, 30, 59, "QF22md"),
    ("OH2BH", 224, 18, 18, "KP20ij"),
    ("EA8AH", 29, 33, 36, "IL18qi"),
    ("9A1A", 497, 15, 28, "JN85fs"),
    ("OK1CF", 503, 15, 28, "JO70fd"),
    ("SP7DQR", 269, 15, 28, "KO01gd"),
    ("UA3QNS", 54, 16, 29, "KO85ws"),
    ("HS0ZAR", 387, 26, 49, "OK03fs"),
    ("BV2AAA", 386, 24, 44, "PL05ef"),
    ("HZ1TT", 378, 21, 39, "KL71ac"),
    ("A71A", 376, 21, 39, "LL55ii"),
    ("ZS6BKW", 462, 38, 57, "KG44dc"),
    ("5B4AIF", 215, 20, 39, "KM64mv"),
    ("FR5ZX", 453, 39, 53, "LG79ni"),
    ("FY5KE", 63, 9, 12, "GJ35ac"),
    ("VP8LP", 141, 13, 16, "GD18oa"),
    ("CE3CT", 112, 12, 14, "FF46pk"),
    ("TI2CF", 308, 7, 11, "EJ09ts"),
    ("XE1RCS", 50, 6, 10, "DL80ff"),
    ("HC2AO", 120, 10, 12, "FI07qe"),
]

OTHER_CALLS = [s[0] for s in OTHER_STATIONS]
STATION_INFO = {s[0]: s[1:] for s in OTHER_STATIONS}


def days_since_epoch(year: int, month: int, day: int) -> int:
    from datetime import date

    return (date(year, month, day) - EPOCH).days


def minutes_from_midnight(hour: int, minute: int) -> int:
    return hour * 60 + minute


class Command(BaseCommand):
    help = "Seed dev database with test data for beau@beaugunderson.com"

    def handle(self, *args, **options):
        user, created = AuthUser.objects.get_or_create(
            username="beau@beaugunderson.com",
            defaults={"email": "beau@beaugunderson.com"},
        )
        if created:
            user.set_password("password")
            user.save()
            self.stdout.write(f"Created user (api_key: {user.api_key})")
        else:
            self.stdout.write("User already exists, resetting data...")
            # Clean up existing seed data
            user_calls = list(
                CallsignAssociation.objects.filter(user=user).values_list(
                    "callsign", flat=True
                )
            )
            mc_ids = list(
                Callsign.objects.filter(callsign__in=user_calls).values_list("id", flat=True)
            )
            if mc_ids:
                Contact.objects.filter(from_id__in=mc_ids).delete()
                Match.objects.filter(a_call_id__in=mc_ids).delete()
                Match.objects.filter(b_call_id__in=mc_ids).delete()
            Callsign.objects.filter(callsign__in=user_calls).delete()
            Callsign.objects.filter(callsign__in=OTHER_CALLS).delete()
            CallsignAssociation.objects.filter(user=user).delete()
            LogUpload.objects.filter(user=user).delete()
            AdifMetadata.objects.all().delete()

        # -- Callsign associations --
        assocs = [
            CallsignAssociation(
                callsign="N7YHF", user=user, verified=True,
                name="Beau Gunderson", country="United States",
                grid_square="CN87us", latitude=47.66, longitude=-122.30,
                start_date="2023-06-15", end_date=None,
            ),
            CallsignAssociation(
                callsign="KI7YMU", user=user, verified=True,
                name="Beau Gunderson", country="United States",
                grid_square="CN87us", latitude=47.66, longitude=-122.30,
                start_date="2020-01-10", end_date="2023-06-14",
            ),
            CallsignAssociation(
                callsign="W7RGM", user=user, verified=False,
                name="Radio Games Matching Club", country="United States",
                grid_square="CN87us",
                start_date="2025-01-01", end_date=None,
            ),
        ]
        CallsignAssociation.objects.bulk_create(assocs)
        self.stdout.write(f"Created {len(assocs)} callsign associations")

        # -- Matcher-side callsigns --
        my_calls = ["N7YHF", "KI7YMU", "W7RGM"]
        all_calls = my_calls + OTHER_CALLS
        callsign_objs = Callsign.objects.bulk_create(
            [Callsign(callsign=c) for c in all_calls]
        )
        cs_map = {c.callsign: c.id for c in callsign_objs}
        self.stdout.write(f"Created {len(cs_map)} matcher callsigns")

        # -- ADIF metadata --
        meta = AdifMetadata.objects.create(
            process_time=int(time.time()),
            file_hash="seeddev_fake_hash_001",
            adif_version="3.1.4",
            program_id="seeddev",
            program_version="1.0",
        )

        # -- Uploads (mark as processed) --
        LogUpload.objects.create(
            log_file="uploads/seed/n7yhf_2025.adi",
            callsign="N7YHF", user=user, processed=True,
        )
        LogUpload.objects.create(
            log_file="uploads/seed/ki7ymu_2024.adi",
            callsign="KI7YMU", user=user, processed=True,
        )
        LogUpload.objects.create(
            log_file="uploads/seed/n7yhf_latest.adi",
            callsign="N7YHF", user=user, processed=False,
        )
        self.stdout.write("Created 3 log uploads (2 processed, 1 pending)")

        # -- Contacts --
        rng = random.Random(42)  # deterministic
        contacts = []

        # QSOs as N7YHF (current call) — bulk, spanning several months
        band_mode_combos = [
            (BAND_20M, MODE_FT8, 0),
            (BAND_40M, MODE_FT8, 0),
            (BAND_15M, MODE_FT4, SUB_FT4),
            (BAND_10M, MODE_SSB, SUB_USB),
            (BAND_80M, MODE_CW, 0),
            (BAND_2M, MODE_SSB, SUB_USB),
            (BAND_70CM, MODE_SSB, SUB_USB),
            (BAND_20M, MODE_SSB, SUB_LSB),
            (BAND_40M, MODE_CW, 0),
        ]

        for i in range(200):
            day_offset = rng.randint(0, 180)
            d = days_since_epoch(2025, 1, 1) + day_offset
            hour = rng.randint(0, 23)
            minute = rng.randint(0, 59)
            t = minutes_from_midnight(hour, minute)
            other = rng.choice(OTHER_CALLS)
            band, mode, sub = rng.choice(band_mode_combos)
            dxcc, cq, itu, grid_str = STATION_INFO[other]
            grid_num, grid_len = encode_grid(grid_str)

            contacts.append(Contact(
                adif_metadata_id=meta.id,
                date=d, time=t, time_off=0,
                from_id=cs_map["N7YHF"], to_id=cs_map[other],
                band=band, mode=mode, sub_mode=sub,
                grid=grid_num, grid_size=grid_len, dxcc=dxcc,
                zone_cq=cq, zone_itu=itu, tx_power=0,
            ))

        # QSOs as KI7YMU (old call) — fewer, older
        for i in range(30):
            day_offset = rng.randint(0, 365)
            d = days_since_epoch(2022, 1, 1) + day_offset
            hour = rng.randint(0, 23)
            minute = rng.randint(0, 59)
            t = minutes_from_midnight(hour, minute)
            other = rng.choice(OTHER_CALLS[:15])  # fewer DX contacts on old call
            band, mode, sub = rng.choice(band_mode_combos[:5])
            dxcc, cq, itu, grid_str = STATION_INFO[other]
            grid_num, grid_len = encode_grid(grid_str)

            contacts.append(Contact(
                adif_metadata_id=meta.id,
                date=d, time=t, time_off=0,
                from_id=cs_map["KI7YMU"], to_id=cs_map[other],
                band=band, mode=mode, sub_mode=sub,
                grid=grid_num, grid_size=grid_len, dxcc=dxcc,
                zone_cq=cq, zone_itu=itu, tx_power=0,
            ))

        Contact.objects.bulk_create(contacts)
        # Refresh to get IDs
        my_matcher_ids = [cs_map["N7YHF"], cs_map["KI7YMU"], cs_map["W7RGM"]]
        all_contacts = list(
            Contact.objects.filter(from_id__in=my_matcher_ids).order_by("id")
        )
        self.stdout.write(f"Created {len(all_contacts)} contacts")

        # -- "Other side" contacts + matches --
        # Simulate the other station also uploading — ~40% confirmation rate
        other_contacts = []
        match_pairs = []

        # Sample refs for other-side contacts
        pota_parks = [
            "K-0059", "K-0817", "K-4566", "K-1234", "K-9876",
            "VE-0012", "G-0001", "DL-0042", "JA-0003",
        ]
        sota_summits = ["W7W/KG-049", "W7W/LC-001", "W1/CR-001", "G/LD-001", "DL/AL-001"]
        wwff_refs = ["KFF-0059", "KFF-1234", "DLFF-0042", "JAFF-0003"]
        iota_refs = ["NA-065", "EU-005", "OC-001", "SA-008", "AF-032"]

        for c in all_contacts:
            if rng.random() < 0.4:
                # Other station's contact: from=them, to=me, within 30 min
                time_delta = rng.randint(-15, 15)
                other_time = max(0, min(1439, c.time + time_delta))

                # ~30% of matched contacts have ref data
                ref_kwargs: dict = {}
                r = rng.random()
                if r < 0.15:
                    # POTA activation (sometimes multi-park)
                    n_parks = rng.choice([1, 1, 1, 2])
                    ref_kwargs["my_pota"] = rng.sample(pota_parks, n_parks)
                elif r < 0.22:
                    ref_kwargs["my_sota"] = rng.choice(sota_summits)
                elif r < 0.26:
                    ref_kwargs["my_wwff"] = rng.choice(wwff_refs)
                elif r < 0.30:
                    ref_kwargs["my_iota"] = rng.choice(iota_refs)

                oc = Contact(
                    adif_metadata_id=meta.id,
                    date=c.date, time=other_time, time_off=0,
                    from_id=c.to_id, to_id=c.from_id,
                    band=c.band, mode=c.mode, sub_mode=c.sub_mode,
                    grid=0, grid_size=0, dxcc=0,
                    zone_cq=0, zone_itu=0, tx_power=0,
                    **ref_kwargs,
                )
                other_contacts.append((c, oc))

        Contact.objects.bulk_create([oc for _, oc in other_contacts])
        # Refresh to get IDs for the other-side contacts
        other_ids = list(
            Contact.objects.filter(from_id__in=[cs_map[c] for c in OTHER_CALLS])
            .order_by("-id")[: len(other_contacts)]
            .values_list("id", flat=True)
        )
        # Re-fetch in insertion order
        other_objs = list(Contact.objects.filter(id__in=other_ids).order_by("id"))

        now_ts = int(time.time())
        matches = []
        for (my_c, _), their_c in zip(other_contacts, other_objs):
            a_id, b_id = sorted([my_c.id, their_c.id])
            matches.append(Match(
                matched_at=now_ts - rng.randint(0, 86400 * 30),
                a_id=a_id, b_id=b_id,
                a_call_id=my_c.from_id, b_call_id=their_c.from_id,
            ))

        Match.objects.bulk_create(matches)
        self.stdout.write(f"Created {len(other_contacts)} reciprocal contacts")
        self.stdout.write(f"Created {len(matches)} matches")

        self.stdout.write(self.style.SUCCESS(
            f"\nDev data seeded. Login: beau@beaugunderson.com / password"
        ))
