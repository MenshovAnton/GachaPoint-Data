import json
import os
import re
import unittest
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLACEMENT_RE = re.compile(r"\?{2,}|\ufffd")
PERMANENT_ALLOWLIST = {
    (0, "GENSHINGIFT"),
    (1, "STARRAILGIFT"),
    (2, "ZENLESSGIFT"),
    (3, "HONKAIGIFT"),
    (1, "CREATIONNYMPH"),
    (1, "FAREWELL"),
    (1, "IFYOUAREREADINGTHIS"),
    (1, "OMEGA"),
}


def load(name):
    with open(os.path.join(BASE_DIR, name), "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


class DataQualityTests(unittest.TestCase):
    def test_no_replacement_characters(self):
        for name in ("promocodes.json", "banners_schedule.json", "game_catalog.json"):
            raw = json.dumps(load(name), ensure_ascii=False)
            self.assertIsNone(REPLACEMENT_RE.search(raw), f"Broken characters in {name}")

    def test_expired_codes_have_no_future_expiry(self):
        now = datetime.now(timezone.utc)
        for entry in load("promocodes.json")["codes"]:
            if entry.get("status") != "EXPIRED":
                continue
            expires_at = parse_iso(entry.get("expires_at"))
            if expires_at is not None:
                self.assertLessEqual(
                    expires_at,
                    now,
                    f"{entry.get('code')} is EXPIRED but expires in the future",
                )

    def test_active_codes_have_source_or_manual_check(self):
        for entry in load("promocodes.json")["codes"]:
            if entry.get("status") not in ("ACTIVE", "STREAM", "NEW"):
                continue
            self.assertEqual(
                entry.get("verification_status"),
                "verified",
                f"{entry.get('code')} is active but not verified",
            )
            self.assertTrue(
                entry.get("source_url") or entry.get("source_type") == "manual_in_game",
                f"{entry.get('code')} has no source",
            )

    def test_permanent_codes_are_allowlisted(self):
        for entry in load("promocodes.json")["codes"]:
            if entry.get("status") != "PERMANENT":
                continue
            key = (entry.get("game_type"), entry.get("code"))
            self.assertIn(key, PERMANENT_ALLOWLIST)

    def test_current_banners_are_verified(self):
        for game in load("banners_schedule.json")["games"]:
            for banner in game.get("banners", []):
                if banner.get("status") not in ("CURRENT", "ANNOUNCED"):
                    continue
                self.assertEqual(
                    banner.get("verification_status"),
                    "verified",
                    f"{banner.get('id')} is not verified",
                )
                self.assertTrue(banner.get("source_url"), f"{banner.get('id')} has no source")
                self.assertTrue(banner.get("source_id"), f"{banner.get('id')} has no source_id")
                self.assertTrue(banner.get("verified_at"), f"{banner.get('id')} has no verified_at")

    def test_quarantine_does_not_contain_published_codes(self):
        published = {
            (entry.get("game_type"), entry.get("code"))
            for entry in load("promocodes.json")["codes"]
        }
        path = os.path.join(BASE_DIR, "quarantine_codes.json")
        if not os.path.exists(path):
            return
        for entry in load("quarantine_codes.json").get("codes", []):
            self.assertNotIn((entry.get("game_type"), entry.get("code")), published)


if __name__ == "__main__":
    unittest.main()
