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
from datetime import datetime, date
from typing import Dict, List, Set, Tuple, Any

BANNER_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")

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

            if not rarity or not any(s in rarity for s in ["3★", "4★", "5★", "S", "A", "B"]):
                warnings.append(f"Game {gt} item '{display_name}': unexpected rarity '{rarity}'")

            if item_type not in ["CHARACTER", "WEAPON", "BANGBOO", "ASTRAL_OP", "ELF"]:
                warnings.append(f"Game {gt} item '{display_name}': unknown type '{item_type}'")

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

            if s_date and e_date and BANNER_DATE_RE.match(s_date) and BANNER_DATE_RE.match(e_date):
                start = date.fromisoformat(s_date)
                end = date.fromisoformat(e_date)
                expected = "ANNOUNCED" if today < start else ("CURRENT" if start <= today <= end else "EXPIRED")
                if b.get("status") != expected:
                    errors.append(
                        f"Game {gt} banner '{b_id}': status '{b.get('status')}' does not match dates (expected {expected})"
                    )

            fives_ru = b.get("featured_five_stars_ru", [])
            fives_en = b.get("featured_five_stars_en", [])
            fours_ru = b.get("featured_four_stars_ru", [])
            fours_en = b.get("featured_four_stars_en", [])

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
        (2, "ZZZTVCM"),
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

        if status == "PERMANENT":
            found_perms.add(pair)

        if "rewards_description" in c:
            errors.append(f"promocodes.json code '{code_str}': deprecated field 'rewards_description' must be removed")

        desc_ru = (c.get("rewards_description_ru") or "").strip()
        desc_en = (c.get("rewards_description_en") or "").strip()
        if not desc_ru or not desc_en:
            errors.append(f"promocodes.json code '{code_str}': both RU and EN rewards descriptions are required")

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

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    strict = "--strict" in sys.argv
    print("=== GachaPoint Data Hub Linting & Validation ===")

    catalog_lookup, cat_errors, cat_warnings = lint_catalog(base_dir)
    banner_errors, banner_warnings = lint_banners(base_dir, catalog_lookup)
    promo_errors, promo_warnings = lint_promocodes(base_dir)

    all_errors = cat_errors + banner_errors + promo_errors
    all_warnings = cat_warnings + banner_warnings + promo_warnings

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
