#!/usr/bin/env python3
"""
GachaPoint Data Hub — Strict Linter & Integrity Validator
Verifies schemas, catalog-to-banner entity cross-referencing,
avatar asset availability, and formatting rules.
Can be run locally or in GitHub Actions CI.
"""

import os
import sys
import json
import re
import urllib.parse
from datetime import datetime, date, timezone
from typing import Dict, List, Set, Tuple, Any

BANNER_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")
REPLACEMENT_RE = re.compile(r"\?{2,}|\ufffd")
OFFICIAL_HOSTS = ("hoyoverse.com", "hoyolab.com", "x.com", "twitter.com")
VERIFICATION_VALUES = {"verified", "legacy", "unverified"}
EXPIRY_CONFIDENCE_VALUES = {"official", "estimated", "unknown"}
SOURCE_TYPES = {"official", "manual_in_game", "community"}
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
ALLOWED_RARITIES = {
    0: {"4★", "5★"},
    1: {"4★", "5★"},
    2: {"A", "S"},
    3: {"A", "B", "S"},
}


def is_official_url(value: str) -> bool:
    try:
        host = urllib.parse.urlparse(value).hostname or ""
    except Exception:
        return False
    return any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_HOSTS)


def is_detail_url(value: str) -> bool:
    try:
        path = (urllib.parse.urlparse(value).path or "").rstrip("/")
    except Exception:
        return False
    if not path:
        return False
    generic = {"/en/news", "/ru/news", "/en-us/news", "/global/en/news"}
    return path not in generic and not path.endswith("/news")


def parse_iso(value: str) -> Any:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

def normalize_name(s: str) -> str:
    if not s:
        return ""
    return s.strip().lower().replace("ё", "е")

def load_json(path: str) -> Any:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def lint_catalog(base_dir: str) -> Tuple[Dict[int, Dict[str, Any]], List[str], List[str]]:
    catalog_path = os.path.join(base_dir, "game_catalog.json")
    errors = []
    warnings = []
    lookup = {0: {}, 1: {}, 2: {}, 3: {}}

    try:
        data = load_json(catalog_path)
    except Exception as e:
        return lookup, [f"Failed to load game_catalog.json: {e}"], []

    if data.get("schema_version") != 1:
        errors.append("game_catalog.json: 'schema_version' must be 1")
    if "version" in data:
        errors.append("game_catalog.json: deprecated top-level 'version' must be replaced by 'schema_version'")

    games = data.get("games", [])
    if not games:
        errors.append("game_catalog.json: 'games' list is empty or missing")
        return lookup, errors, warnings

    for g in games:
        gt = g.get("game_type")
        if gt not in [0, 1, 2, 3]:
            errors.append(f"game_catalog.json: invalid game_type '{gt}'")
            continue

        items = g.get("items", [])
        seen_names = set()
        seen_en = set()
        seen_icons = set()

        for idx, item in enumerate(items):
            name_ru = item.get("name_ru")
            name_en = item.get("name_en")
            display_name = name_ru or name_en
            icon_path = item.get("icon_path", "")
            rarity = item.get("rarity")
            item_type = item.get("type")
            aliases = item.get("aliases", [])

            if REPLACEMENT_RE.search(name_ru or "") or REPLACEMENT_RE.search(name_en or ""):
                errors.append(f"Game {gt} item #{idx}: broken characters in localized name")
                continue

            if not name_ru or not name_en:
                errors.append(f"Game {gt} item #{idx}: missing 'name_ru' or 'name_en'")
                continue

            if "name" in item:
                errors.append(f"Game {gt} item '{display_name}': deprecated field 'name' must be removed")

            if "icon_url" in item:
                errors.append(f"Game {gt} item '{display_name}': deprecated field 'icon_url' must be replaced by 'icon_path'")

            norm_name = normalize_name(name_ru)
            if norm_name in seen_names:
                errors.append(f"Game {gt}: duplicate name_ru '{name_ru}'")
            seen_names.add(norm_name)

            norm_en = normalize_name(name_en)
            if norm_en in seen_en:
                warnings.append(f"Game {gt}: duplicate name_en '{name_en}'")
            seen_en.add(norm_en)

            if icon_path:
                if icon_path in seen_icons:
                    warnings.append(f"Game {gt}: duplicate icon_path '{icon_path}' for '{display_name}'")
                seen_icons.add(icon_path)

                local_avatar = os.path.join(base_dir, icon_path.replace("/", os.sep))
                if not os.path.exists(local_avatar):
                    warnings.append(f"Game {gt} item '{display_name}': avatar file not found locally: {icon_path}")

            if rarity not in ALLOWED_RARITIES.get(gt, set()):
                errors.append(f"Game {gt} item '{display_name}': unexpected rarity '{rarity}'")

            if item_type not in ["CHARACTER", "WEAPON", "BANGBOO", "ASTRAL_OP", "ELF"]:
                warnings.append(f"Game {gt} item '{display_name}': unknown type '{item_type}'")

            if not isinstance(item.get("is_standard"), bool):
                errors.append(f"Game {gt} item '{display_name}': 'is_standard' must be a boolean")



            # Register in lookup for banner validation
            keys = [name_ru, name_en] + aliases
            for k in keys:
                if k:
                    lookup[gt][normalize_name(k)] = item

    return lookup, errors, warnings

def lint_banners(base_dir: str, catalog_lookup: Dict[int, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    banners_path = os.path.join(base_dir, "banners_schedule.json")
    errors = []
    warnings = []

    try:
        data = load_json(banners_path)
    except Exception as e:
        return [f"Failed to load banners_schedule.json: {e}"], []

    if data.get("schema_version") != 1:
        errors.append("banners_schedule.json: 'schema_version' must be 1")
    if "version" in data:
        errors.append("banners_schedule.json: deprecated top-level 'version' must be replaced by 'schema_version'")

    today = date.today()
    special_types = {"CHRONICLED", "LIGHTRACE", "COLLAB", "EXPANSION", "EXPA_SELECT"}

    games = data.get("games", [])
    for g in games:
        gt = g.get("game_type")
        if gt not in catalog_lookup:
            errors.append(f"banners_schedule.json: unknown game_type {gt}")
            continue

        banners = g.get("banners", [])
        patch_by_version = {}
        for patch in g.get("patches", []):
            if patch.get("version"):
                patch_by_version[patch["version"]] = patch

        seen_ids = set()
        for idx, b in enumerate(banners):
            b_id = b.get("id", f"idx_{idx}")
            version = b.get("version")
            phase = b.get("phase")
            s_date = b.get("start_date")
            e_date = b.get("end_date")

            if b_id in seen_ids:
                errors.append(f"Game {gt}: duplicate banner id '{b_id}'")
            seen_ids.add(b_id)

            if not version:
                errors.append(f"Game {gt} banner '{b_id}': missing 'version'")
            if phase not in [1, 2, 3]:
                warnings.append(f"Game {gt} banner '{b_id}': uncommon phase '{phase}'")

            if not s_date or not BANNER_DATE_RE.match(s_date):
                errors.append(f"Game {gt} banner '{b_id}': invalid start_date '{s_date}'")
            if not e_date or not BANNER_DATE_RE.match(e_date):
                errors.append(f"Game {gt} banner '{b_id}': invalid end_date '{e_date}'")

            if s_date and e_date and s_date > e_date:
                errors.append(f"Game {gt} banner '{b_id}': start_date '{s_date}' is after end_date '{e_date}'")

            expected = None
            if s_date and e_date and BANNER_DATE_RE.match(s_date) and BANNER_DATE_RE.match(e_date):
                try:
                    start = date.fromisoformat(s_date)
                    end = date.fromisoformat(e_date)
                except ValueError:
                    errors.append(
                        f"Game {gt} banner '{b_id}': invalid calendar date '{s_date}'/'{e_date}'"
                    )
                else:
                    expected = "ANNOUNCED" if today < start else ("CURRENT" if start <= today <= end else "EXPIRED")
                    if b.get("status") != expected:
                        errors.append(
                            f"Game {gt} banner '{b_id}': status '{b.get('status')}' does not match dates (expected {expected})"
                        )

            if b.get("verification_status") is not None and b.get("verification_status") not in VERIFICATION_VALUES:
                errors.append(
                    f"Game {gt} banner '{b_id}': invalid verification_status '{b.get('verification_status')}'"
                )

            if b.get("source_url") and not is_official_url(b["source_url"]):
                errors.append(
                    f"Game {gt} banner '{b_id}': source_url is not an official HoYoverse source"
                )

            if b.get("source_type") is not None and b.get("source_type") not in SOURCE_TYPES:
                errors.append(
                    f"Game {gt} banner '{b_id}': invalid source_type '{b.get('source_type')}'"
                )

            if expected in ("CURRENT", "ANNOUNCED"):
                if not b.get("source_url"):
                    errors.append(
                        f"Game {gt} banner '{b_id}': CURRENT/ANNOUNCED banner requires an official source_url"
                    )
                elif not is_detail_url(b["source_url"]):
                    errors.append(
                        f"Game {gt} banner '{b_id}': source_url must point to a specific post, not a news index"
                    )
                if not b.get("source_id"):
                    errors.append(
                        f"Game {gt} banner '{b_id}': CURRENT/ANNOUNCED banner requires 'source_id'"
                    )
                if b.get("verification_status") != "verified":
                    errors.append(
                        f"Game {gt} banner '{b_id}': CURRENT/ANNOUNCED banner must have verification_status 'verified'"
                    )
                if not b.get("verified_at"):
                    errors.append(
                        f"Game {gt} banner '{b_id}': verified banner requires 'verified_at'"
                    )

            fives_ru = b.get("featured_five_stars_ru", [])
            fives_en = b.get("featured_five_stars_en", [])
            fours_ru = b.get("featured_four_stars_ru", [])
            fours_en = b.get("featured_four_stars_en", [])

            for names in (fives_ru, fives_en, fours_ru, fours_en):
                for name in names:
                    if REPLACEMENT_RE.search(name or ""):
                        errors.append(
                            f"Game {gt} banner '{b_id}': broken characters in featured name '{name}'"
                        )
            if len(fives_ru) != len(fives_en):
                errors.append(f"Game {gt} banner '{b_id}': 5-star RU/EN lists have different lengths")
            if len(fours_ru) != len(fours_en):
                errors.append(f"Game {gt} banner '{b_id}': 4-star RU/EN lists have different lengths")

            if "featured_five_stars" in b or "featured_four_stars" in b:
                errors.append(
                    f"Game {gt} banner '{b_id}': deprecated base fields 'featured_five_stars'/'featured_four_stars' must be removed"
                )

            if not fives_ru or not fives_en:
                errors.append(f"Game {gt} banner '{b_id}': both 'featured_five_stars_ru' and 'featured_five_stars_en' are required")

            if "type" not in b:
                errors.append(f"Game {gt} banner '{b_id}': missing 'type'")

            if version in patch_by_version and phase == 1 and s_date:
                patch_start = patch_by_version[version].get("start_date")
                if patch_start and s_date != patch_start:
                    warnings.append(
                        f"Game {gt} banner '{b_id}': start_date '{s_date}' != patch {version} start '{patch_start}'"
                    )

            for char_name in fives_ru + fives_en:
                if char_name and normalize_name(char_name) not in catalog_lookup[gt]:
                    warnings.append(f"Game {gt} banner '{b_id}': 5★ '{char_name}' not resolved in catalog")

            for char_name in fours_ru + fours_en:
                if char_name and normalize_name(char_name) not in catalog_lookup[gt]:
                    warnings.append(f"Game {gt} banner '{b_id}': 4★ '{char_name}' not resolved in catalog")

        for i, a in enumerate(banners):
            a_start = a.get("start_date")
            a_end = a.get("end_date")
            if not a_start or not a_end or not BANNER_DATE_RE.match(a_start) or not BANNER_DATE_RE.match(a_end):
                continue
            for b in banners[i + 1:]:
                b_start = b.get("start_date")
                b_end = b.get("end_date")
                if not b_start or not b_end or not BANNER_DATE_RE.match(b_start) or not BANNER_DATE_RE.match(b_end):
                    continue
                if a.get("type", "").upper() in special_types or b.get("type", "").upper() in special_types:
                    continue
                if a_end == b_start or b_end == a_start:
                    continue
                if a_start < b_end and b_start < a_end:
                    warnings.append(
                        f"Game {gt}: banners '{a.get('id')}' and '{b.get('id')}' overlap without a special type"
                    )

        if gt in (0, 1, 2):
            intervals = []
            for b in banners:
                s = b.get("start_date")
                e = b.get("end_date")
                if s and e and BANNER_DATE_RE.match(s) and BANNER_DATE_RE.match(e):
                    intervals.append((date.fromisoformat(s), date.fromisoformat(e), b.get("id")))
            intervals.sort()
            for (s1, e1, id1), (s2, e2, id2) in zip(intervals, intervals[1:]):
                gap = (s2 - e1).days
                if gap > 90 and s2 >= date(2024, 1, 1):
                    warnings.append(
                        f"Game {gt}: {gap}-day coverage gap between '{id1}' and '{id2}'"
                    )

    return errors, warnings

def lint_promocodes(base_dir: str) -> Tuple[List[str], List[str]]:
    promo_path = os.path.join(base_dir, "promocodes.json")
    errors = []
    warnings = []
    now = datetime.now(timezone.utc)

    try:
        data = load_json(promo_path)
    except Exception as e:
        return [f"Failed to load promocodes.json: {e}"], []

    if data.get("schema_version") != 1:
        errors.append("promocodes.json: 'schema_version' must be 1")
    if "version" in data:
        errors.append("promocodes.json: deprecated top-level 'version' must be replaced by 'schema_version'")

    codes = data.get("codes", [])
    if not codes or len(codes) < 5:
        errors.append("promocodes.json: codes list is too short or empty")
        return errors, warnings

    seen_codes = set()
    mandatory_perms = {
        (0, "GENSHINGIFT"),
        (1, "STARRAILGIFT"),
        (2, "ZENLESSGIFT"),
        (3, "HONKAIGIFT")
    }

    found_perms = set()

    for idx, c in enumerate(codes):
        code_str = c.get("code")
        gt = c.get("game_type")
        status = c.get("status")

        if not code_str or not CODE_RE.match(code_str):
            errors.append(f"promocodes.json code #{idx}: invalid code format '{code_str}'")
            continue

        pair = (gt, code_str)
        if pair in seen_codes:
            errors.append(f"promocodes.json: duplicate code '{code_str}' for game {gt}")
        seen_codes.add(pair)

        status_upper = (status or "").upper()
        expires_at = parse_iso(c.get("expires_at"))

        if status_upper == "PERMANENT":
            if pair not in PERMANENT_ALLOWLIST:
                errors.append(f"promocodes.json code '{code_str}': unexpected PERMANENT status")
            if c.get("expires_at"):
                errors.append(f"promocodes.json code '{code_str}': PERMANENT code must not have expires_at")

        if status_upper in ("ACTIVE", "STREAM", "NEW"):
            if expires_at is not None and expires_at < now:
                errors.append(f"promocodes.json code '{code_str}': active code has a past expires_at")
            if not c.get("source_url") and c.get("source_type") != "manual_in_game":
                errors.append(
                    f"promocodes.json code '{code_str}': active code requires source_url or source_type 'manual_in_game'"
                )
            if c.get("source_type") == "manual_in_game" and not c.get("verified_at"):
                errors.append(
                    f"promocodes.json code '{code_str}': manual_in_game code requires 'verified_at'"
                )

        if status_upper == "EXPIRED" and expires_at is not None and expires_at > now:
            errors.append(f"promocodes.json code '{code_str}': expired code has a future expires_at")

        if c.get("source_type") is not None and c.get("source_type") not in SOURCE_TYPES:
            errors.append(f"promocodes.json code '{code_str}': invalid source_type '{c.get('source_type')}'")

        if c.get("source_url") and not is_detail_url(c["source_url"]):
            errors.append(f"promocodes.json code '{code_str}': source_url must point to a specific post")

        if status == "PERMANENT":
            found_perms.add(pair)

        if status in ("ACTIVE", "STREAM", "NEW") and c.get("verification_status") != "verified":
            errors.append(f"promocodes.json code '{code_str}': active/stream code must be verified")

        if status in ("ACTIVE", "STREAM", "NEW") and c.get("expiry_confidence") == "estimated":
            errors.append(f"promocodes.json code '{code_str}': active code cannot use an estimated expiry")

        if c.get("expiry_confidence") == "unknown" and c.get("expires_at"):
            errors.append(f"promocodes.json code '{code_str}': unknown expiry must not have expires_at")

        if c.get("verification_status") is not None and c.get("verification_status") not in VERIFICATION_VALUES:
            errors.append(f"promocodes.json code '{code_str}': invalid verification_status '{c.get('verification_status')}'")

        if c.get("source_url") and not is_official_url(c["source_url"]):
            errors.append(f"promocodes.json code '{code_str}': source_url is not an official HoYoverse source")

        if c.get("expiry_confidence") is not None and c.get("expiry_confidence") not in EXPIRY_CONFIDENCE_VALUES:
            errors.append(f"promocodes.json code '{code_str}': invalid expiry_confidence '{c.get('expiry_confidence')}'")

        if "rewards_description" in c:
            errors.append(f"promocodes.json code '{code_str}': deprecated field 'rewards_description' must be removed")

        desc_ru = (c.get("rewards_description_ru") or "").strip()
        desc_en = (c.get("rewards_description_en") or "").strip()
        if not desc_ru or not desc_en:
            errors.append(f"promocodes.json code '{code_str}': both RU and EN rewards descriptions are required")
        if REPLACEMENT_RE.search(desc_ru) or REPLACEMENT_RE.search(desc_en):
            errors.append(f"promocodes.json code '{code_str}': broken characters in rewards description")

        bare_placeholders = {
            "камни истока", "звёздный нефрит", "звездный нефрит", "полихромы", "кристаллы",
            "primogems", "stellar jade", "polychromes", "crystals"
        }
        if desc_ru.lower() in bare_placeholders or desc_en.lower() in bare_placeholders:
            errors.append(f"promocodes.json code '{code_str}': rewards description cannot be bare currency name without quantity ('{desc_ru}')")

    missing_perms = mandatory_perms - found_perms
    if missing_perms:
        errors.append(f"promocodes.json: missing mandatory permanent codes: {missing_perms}")

    return errors, warnings

def lint_quarantine(base_dir: str) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []

    try:
        promo = load_json(os.path.join(base_dir, "promocodes.json"))
    except Exception:
        return errors, warnings
    published_codes = {
        (code.get("game_type", 0), (code.get("code") or "").strip().upper())
        for code in promo.get("codes", [])
    }

    quarantine_path = os.path.join(base_dir, "quarantine_codes.json")
    if os.path.exists(quarantine_path):
        try:
            quarantine = load_json(quarantine_path)
            for entry in quarantine.get("codes", []):
                code = (entry.get("code") or "").strip().upper()
                game_type = entry.get("game_type", 0)
                if not code or not CODE_RE.match(code):
                    errors.append(f"quarantine_codes.json: invalid code '{code}'")
                if (game_type, code) in published_codes:
                    errors.append(
                        f"quarantine_codes.json: code '{code}' is already published in promocodes.json"
                    )
        except Exception as e:
            errors.append(f"Failed to load quarantine_codes.json: {e}")

    pending_path = os.path.join(base_dir, "pending_banners.json")
    banners_path = os.path.join(base_dir, "banners_schedule.json")
    if os.path.exists(pending_path) and os.path.exists(banners_path):
        try:
            pending = load_json(pending_path)
            banners = load_json(banners_path)
            published_ids = {
                (game.get("game_type", 0), banner.get("id", ""))
                for game in banners.get("games", [])
                for banner in game.get("banners", [])
            }
            for entry in pending.get("banners", []):
                key = (entry.get("game_type", 0), entry.get("id", ""))
                if key in published_ids:
                    errors.append(
                        f"pending_banners.json: banner '{key[1]}' is already published in banners_schedule.json"
                    )
        except Exception as e:
            errors.append(f"Failed to load pending_banners.json: {e}")

    return errors, warnings


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    strict = "--strict" in sys.argv
    print("=== GachaPoint Data Hub Linting & Validation ===")

    catalog_lookup, cat_errors, cat_warnings = lint_catalog(base_dir)
    banner_errors, banner_warnings = lint_banners(base_dir, catalog_lookup)
    promo_errors, promo_warnings = lint_promocodes(base_dir)
    quarantine_errors, quarantine_warnings = lint_quarantine(base_dir)

    all_errors = cat_errors + banner_errors + promo_errors + quarantine_errors
    all_warnings = cat_warnings + banner_warnings + promo_warnings + quarantine_warnings

    print(f"\n[CATALOG] {sum(len(v) for v in catalog_lookup.values())} indexed lookup names across 4 games.")
    print(f"[RESULTS] Errors: {len(all_errors)}, Warnings: {len(all_warnings)}")

    if all_warnings:
        print("\n--- WARNINGS ---")
        for w in all_warnings[:25]:
            print(f" [!] {w}")
        if len(all_warnings) > 25:
            print(f" ... and {len(all_warnings) - 25} more warnings.")

    if all_errors:
        print("\n--- ERRORS ---")
        for e in all_errors:
            print(f" [X] {e}")
        print("\nLint failed with ERRORS.")
        sys.exit(1)

    if all_warnings and strict:
        print("\nLint failed in strict mode due to WARNINGS.")
        sys.exit(1)

    print("\nLint PASSED (zero blocking errors).")
    sys.exit(0)

if __name__ == "__main__":
    main()
