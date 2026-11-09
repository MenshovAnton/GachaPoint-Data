import unittest

from scripts.parsers.fandom_parser import extract_source_url, parse_section_rows
from scripts.parsers.official_codes_parser import (
    discover_official_codes,
    verify_code,
)


def source(game_type, text, url="https://www.hoyolab.com/article/1", source_id="1"):
    return {
        "game_type": game_type,
        "title": "Official post",
        "url": url,
        "source_id": source_id,
        "text": text,
    }


class OfficialCodeVerificationTests(unittest.TestCase):
    def test_verified_when_official_text_has_rewards(self):
        text = (
            "Use promo code ABC123 to receive 60 Primogems and 10,000 Mora. "
            "The code is valid until 2026/11/24 23:59."
        )
        result = verify_code(0, "ABC123", [source(0, text)])
        self.assertEqual(result["status"], "verified")
        self.assertIn("60", result["rewards_description_en"])
        self.assertEqual(result["expires_at"], "2026-11-24T23:59:59Z")
        self.assertEqual(result["expiry_confidence"], "official")

    def test_ambiguous_when_code_found_without_rewards(self):
        result = verify_code(0, "ABC123", [source(0, "Use promo code ABC123 during the event.")])
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["rewards_description_en"])

    def test_not_found_when_code_is_absent(self):
        result = verify_code(0, "ABC123", [source(0, "No codes here.")])
        self.assertEqual(result["status"], "not_found")

    def test_ignores_other_games(self):
        result = verify_code(0, "ABC123", [source(1, "Promo code ABC123 gives 60 Stellar Jade.")])
        self.assertEqual(result["status"], "not_found")

    def test_discovery_requires_context_and_digit(self):
        text = (
            "Promo code: ZZZ12345. "
            "The Version 3.3 update is live. "
            "Use code UPDATE for nothing."
        )
        codes = [entry["code"] for entry in discover_official_codes([source(2, text)])]
        self.assertIn("ZZZ12345", codes)
        self.assertNotIn("UPDATE", codes)


class FandomSourceTests(unittest.TestCase):
    def test_extracts_official_source_url(self):
        row = (
            '{{Code Row|KeepUpWithMitya|G|Guide to Charity*3|2026-11-04|unknown'
            '|ref=<ref>Hoyoverse: [https://genshin.hoyoverse.com/en/news/detail/167189 Event]</ref>}}'
        )
        self.assertEqual(
            extract_source_url(row),
            "https://genshin.hoyoverse.com/en/news/detail/167189",
        )

    def test_ignores_non_official_source_url(self):
        row = '{{Code Row|TESTCODE123|G|Primogem*60|2026-11-01|unknown|ref=<ref>https://example.com</ref>}}'
        self.assertIsNone(extract_source_url(row))

    def test_parse_section_rows_keeps_source_url(self):
        row = (
            '{{Code Row|TESTCODE123|G|Primogem*60|2026-11-01|unknown'
            '|ref=<ref>[https://genshin.hoyoverse.com/en/news/detail/1]</ref>}}'
        )
        items = parse_section_rows(row, 0, is_section_expired=False, seen_codes=set())
        self.assertEqual(len(items), 1)
        self.assertEqual(
            items[0]["source_url"],
            "https://genshin.hoyoverse.com/en/news/detail/1",
        )


if __name__ == "__main__":
    unittest.main()
