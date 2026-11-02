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
from datetime import datetime
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
        seen_icons = set()

        for idx, item in enumerate(items):
            name = item.get("name")
            name_ru = item.get("name_ru") or name
            name_en = item.get("name_en") or name
            icon_url = item.get("icon_url", "")
            rarity = item.get("rarity")
            item_type = item.get("type")
            aliases = item.get("aliases", [])

            if not name:
                errors.append(f"Game {gt} item #{idx}: missing 'name'")
                continue

            norm_name = normalize_name(name)
            if norm_name in seen_names:
                errors.append(f"Game {gt}: duplicate item name '{name}'")
            seen_names.add(norm_name)

            if icon_url:
                if icon_url in seen_icons:
                    warnings.append(f"Game {gt}: duplicate icon_url '{icon_url}' for '{name}'")
                seen_icons.add(icon_url)

                # Check if file exists locally in avatars/{gt}/
                avatar_leaf = os.path.basename(icon_url)
                local_avatar = os.path.join(base_dir, "avatars", str(gt), avatar_leaf)
                if not os.path.exists(local_avatar):
                    warnings.append(f"Game {gt} item '{name}': avatar file not found locally: avatars/{gt}/{avatar_leaf}")

            if not rarity or not any(s in rarity for s in ["3★", "4★", "5★", "S", "A", "B"]):
                warnings.append(f"Game {gt} item '{name}': unexpected rarity '{rarity}'")

            if item_type not in ["CHARACTER", "WEAPON", "BANGBOO", "ASTRAL_OP", "ELF"]:
                warnings.append(f"Game {gt} item '{name}': unknown type '{item_type}'")

            # Register in lookup for banner validation
            keys = [name, name_ru, name_en] + aliases
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

    games = data.get("games", [])
    for g in games:
        gt = g.get("game_type")
        if gt not in catalog_lookup:
            errors.append(f"banners_schedule.json: unknown game_type {gt}")
            continue

        banners = g.get("banners", [])
        for idx, b in enumerate(banners):
            b_id = b.get("id", f"idx_{idx}")
            version = b.get("version")
            phase = b.get("phase")
            s_date = b.get("start_date")
            e_date = b.get("end_date")

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

            fives_ru = b.get("featured_five_stars_ru", [])
            fives_en = b.get("featured_five_stars_en", [])
            fours_ru = b.get("featured_four_stars_ru", [])
            fours_en = b.get("featured_four_stars_en", [])

            # Check matching against catalog
            for char_name in fives_ru + fives_en:
                if char_name and normalize_name(char_name) not in catalog_lookup[gt]:
                    warnings.append(f"Game {gt} banner '{b_id}': 5★ '{char_name}' not resolved in catalog")

            for char_name in fours_ru + fours_en:
                if char_name and normalize_name(char_name) not in catalog_lookup[gt]:
                    warnings.append(f"Game {gt} banner '{b_id}': 4★ '{char_name}' not resolved in catalog")

    return errors, warnings

def lint_promocodes(base_dir: str) -> Tuple[List[str], List[str]]:
    promo_path = os.path.join(base_dir, "promocodes.json")
    errors = []
    warnings = []

    try:
        data = load_json(promo_path)
    except Exception as e:
        return [f"Failed to load promocodes.json: {e}"], []

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

        if not c.get("rewards_description_ru") and not c.get("rewards_description"):
            warnings.append(f"promocodes.json code '{code_str}': missing rewards description")

    missing_perms = mandatory_perms - found_perms
    if missing_perms:
        errors.append(f"promocodes.json: missing mandatory permanent codes: {missing_perms}")

    return errors, warnings

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
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
    else:
        print("\nLint PASSED (zero blocking errors).")
        sys.exit(0)

if __name__ == "__main__":
    main()
