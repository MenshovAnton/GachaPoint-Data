#!/usr/bin/env python3
"""
GachaPoint Data Hub — Autonomous Validation, Moderation & Sync Script

Provides automated data maintenance:
1. Automated web scraping from Fandom MediaWiki API for Genshin, HSR, and ZZZ.
2. Auto-import new promo codes from pending_codes.json or CLI.
3. Strict categorization: PERMANENT, STREAM, ACTIVE, EXPIRED.
4. Banner schedule moderation with calendar-based status updates.
5. Fault tolerance with atomic file writes and Telegram alert notifications.
"""

import json
import os
import re
import sys
import argparse
import traceback
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Safe imports for alerts and parsers
try:
    from scripts.lib.notify import (
        notify_code_review,
        notify_failure,
        notify_new_banners,
        notify_new_codes,
        notify_suspicious_announcement,
    )
except ImportError:
    def notify_failure(summary, details=None):
        print(f"[Alert] Failure: {summary} - {details}")
    def notify_new_codes(new_codes):
        print(f"[Alert] New codes found: {len(new_codes)}")
    def notify_new_banners(new_banners):
        print(f"[Alert] New banners found: {len(new_banners)}")
    def notify_suspicious_announcement(game_name, title, reason, post_url=None):
        print(f"[Alert] Suspicious announcement in {game_name}: {title} ({reason})")
    def notify_code_review(items):
        print(f"[Alert] Codes needing review: {len(items)}")

try:
    from scripts.parsers.fandom_parser import parse_all_games
except ImportError:
    def parse_all_games():
        return []

try:
    from scripts.parsers.official_banners_parser import parse_all_official_data
except ImportError:
    def parse_all_official_data(catalog_path):
        return {"banners": [], "patches": {}, "errors": {}}

try:
    from scripts.parsers.official_codes_parser import verify_candidates
except ImportError:
    def verify_candidates(candidates, sources=None):
        return []

CODE_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,30}$")

BARE_REWARD_DESCRIPTIONS = {
    "камни истока", "звёздный нефрит", "звездный нефрит", "полихромы", "кристаллы",
    "primogems", "stellar jade", "polychromes", "crystals", "mora", "credits",
    "dennies", "coins"
}


def is_placeholder_reward(text: str) -> bool:
    clean = (text or "").strip().lower()
    return not clean or "внутриигровые" in clean or clean in BARE_REWARD_DESCRIPTIONS

PERMANENT_CODES = {
    (0, "GENSHINGIFT"): {
        "rewards_description_ru": "50 Камней Истока, 3 Опыта героя",
        "rewards_description_en": "50 Primogems, 3 Hero's Wit",
        "reward_types": ["PRIMOGEM", "EXP"]
    },
    (1, "STARRAILGIFT"): {
        "rewards_description_ru": "50 Звёздного нефрита, 2 Путеводителя, 10 000 Кредитов",
        "rewards_description_en": "50 Stellar Jade, 2 Traveler's Guide, 10,000 Credits",
        "reward_types": ["JADE", "EXP", "CREDIT"]
    },
    (2, "ZENLESSGIFT"): {
        "rewards_description_ru": "50 Полихромов, 2 Журнала специалиста, 3 Источника питания",
        "rewards_description_en": "50 Polychromes, 2 Official Investigator Logs, 3 W-Engine Power Supplies",
        "reward_types": ["POLYCHROME", "EXP"]
    },
    (3, "HONKAIGIFT"): {
        "rewards_description_ru": "30 Кристаллов, 2 000 Монет",
        "rewards_description_en": "30 Crystals, 2,000 Coins",
        "reward_types": ["CRYSTAL"]
    },
    (1, "CREATIONNYMPH"): {
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (1, "FAREWELL"): {
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (1, "IFYOUAREREADINGTHIS"): {
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (1, "OMEGA"): {
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    }
}


def validate_code(code: str) -> bool:
    if not code:
        return False
    return bool(CODE_REGEX.match(code.strip()))


def parse_iso_datetime(dt_str: str):
    if not dt_str:
        return None
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        try:
            return datetime.strptime(dt_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


def parse_date(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def load_json(filepath: str, default: dict) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8-sig") as f:
            try:
                return json.load(f)
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
    return default


def validate_dataset_before_save(filepath: str, data: dict):
    """Enforces strict safety checks to prevent data loss or corruption."""
    if not isinstance(data, dict):
        raise ValueError(f"Validation failed for {filepath}: data root is not a dictionary")

    if "banners_schedule" in filepath:
        games = data.get("games", [])
        if not games:
            raise ValueError(f"Safety abort: {filepath} has no games")
        banner_count = sum(len(game.get("banners", [])) for game in games)
        if banner_count == 0:
            raise ValueError(f"Safety abort: {filepath} has no banners")
        if os.path.exists(filepath):
            existing = load_json(filepath, {})
            existing_count = sum(
                len(game.get("banners", [])) for game in existing.get("games", [])
            )
            if existing_count and banner_count < existing_count // 2:
                raise ValueError(
                    f"Safety abort: {filepath} banner count dropped "
                    f"from {existing_count} to {banner_count}"
                )

    if "promocodes" in filepath or "codes" in data:
        codes = data.get("codes", [])
        if not codes or len(codes) < 4:
            raise ValueError(f"Safety abort: {filepath} code count ({len(codes)}) below minimum safe threshold")

        existing_perms = {(c.get("game_type"), c.get("code")) for c in codes if c.get("status") == "PERMANENT"}
        mandatory_perms = {
            (0, "GENSHINGIFT"),
            (1, "STARRAILGIFT"),
            (2, "ZENLESSGIFT"),
            (3, "HONKAIGIFT")
        }
        missing_perms = mandatory_perms - existing_perms
        if missing_perms:
            raise ValueError(f"Safety abort: {filepath} is missing mandatory permanent codes: {missing_perms}")


def without_timestamp(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "updated_at"}


def save_json(filepath: str, data: dict) -> bool:
    """Saves JSON atomically via temp file with validation."""
    validate_dataset_before_save(filepath, data)

    if os.path.exists(filepath):
        try:
            existing = load_json(filepath, {})
            if without_timestamp(existing) == without_timestamp(data):
                print(f"No changes for {filepath}")
                return False
        except Exception:
            pass

    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp_path = filepath + ".tmp"

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        # Verify temp file is non-empty and parses cleanly
        with open(tmp_path, "r", encoding="utf-8") as f:
            json.load(f)

        os.replace(tmp_path, filepath)
        print(f"Atomically saved {filepath} (updated_at: {data['updated_at']})")

        # Mirror to Android app assets directory if accessible
        filename = os.path.basename(filepath)
        assets_target = os.path.join(ROOT_DIR, "..", "app", "src", "main", "assets", "data", filename)
        if os.path.exists(os.path.dirname(assets_target)):
            with open(assets_target, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"Mirrored {filename} to Android app assets.")
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise e

    return True


def import_pending_codes(data: dict, pending_file: str = "pending_codes.json") -> Tuple[int, List[Dict[str, Any]]]:
    """Auto-imports new promo codes from buffer file pending_codes.json."""
    if not os.path.exists(pending_file):
        return 0, []

    pending = load_json(pending_file, {})
    new_items = pending.get("codes", []) if isinstance(pending, dict) else pending
    if not isinstance(new_items, list) or not new_items:
        return 0, []

    existing_codes = {(c.get("game_type", 0), c.get("code", "").strip().upper()) for c in data.get("codes", [])}
    added_list = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for item in new_items:
        if isinstance(item, str):
            code_str = item.strip().upper()
            if not validate_code(code_str):
                continue
            item = {"code": code_str, "game_type": 0}

        code_str = item.get("code", "").strip().upper()
        game_type = int(item.get("game_type", 0))
        if not validate_code(code_str) or (game_type, code_str) in existing_codes:
            continue

        item["code"] = code_str
        item["game_type"] = game_type
        if "id" not in item:
            item["id"] = f"code_{game_type}_{code_str.lower()}"
        if "created_at" not in item:
            item["created_at"] = now_iso
        if "is_active" not in item:
            item["is_active"] = True

        data.setdefault("codes", []).append(item)
        existing_codes.add((game_type, code_str))
        added_list.append(item)

    try:
        os.remove(pending_file)
        print(f"Imported {len(added_list)} new codes from {pending_file} and cleared pending queue.")
    except Exception as e:
        print(f"Warning: could not remove {pending_file}: {e}")

    return len(added_list), added_list


def import_scraped_codes(data: dict, scraped_codes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merges verified codes and quarantines unverified candidates."""
    if not scraped_codes:
        return [], []

    existing_map = {(c.get("game_type", 0), c.get("code", "").strip().upper()): c for c in data.get("codes", [])}
    newly_added = []
    pending = []

    for item in scraped_codes:
        g_type = item.get("game_type", 0)
        code_str = item.get("code", "").strip().upper()
        if not validate_code(code_str):
            continue

        item.setdefault("verification_status", "unverified")
        key = (g_type, code_str)
        if key in existing_map:
            existing_item = existing_map[key]
            if item.get("verification_status") == "verified":
                for field in (
                    "status", "is_active", "expires_at", "created_at", "is_stream",
                    "rewards_description_ru", "rewards_description_en", "reward_types",
                    "source_url", "verified_at", "expiry_confidence",
                ):
                    if item.get(field) is not None:
                        existing_item[field] = item[field]
                existing_item["verification_status"] = "verified"
            elif item.get("source_url") and not existing_item.get("source_url"):
                existing_item["source_url"] = item["source_url"]
            continue

        if item.get("status") == "EXPIRED":
            continue

        desc_ru = item.get("rewards_description_ru") or ""
        desc_en = item.get("rewards_description_en") or ""
        has_number = any(ch.isdigit() for ch in desc_ru) or any(ch.isdigit() for ch in desc_en)

        if is_placeholder_reward(desc_ru) or is_placeholder_reward(desc_en) or not has_number:
            game_names = {0: "Genshin Impact", 1: "Honkai: Star Rail", 2: "Zenless Zone Zero", 3: "Honkai Impact 3rd"}
            g_name = game_names.get(g_type, f"Game {g_type}")
            print(f"[Warning] Scraped code {code_str} for {g_name} has no verified reward quantities: '{desc_ru}'")
            notify_suspicious_announcement(g_name, code_str, f"Promo code discovered without verified reward quantities: '{desc_ru}'")
            item["rewards_description_ru"] = "Внутриигровые награды"
            item["rewards_description_en"] = "In-game rewards"
            item["verification_status"] = "unverified"

        if item.get("verification_status") != "verified":
            item["quarantine_reason"] = "unverified_source"
            pending.append(item)
            continue

        data.setdefault("codes", []).append(item)
        existing_map[key] = item
        newly_added.append(item)

    if newly_added:
        print(f"Merged {len(newly_added)} verified promo codes from web scraper.")
    if pending:
        print(f"Quarantined {len(pending)} unverified promo code candidates.")
    return newly_added, pending


def merge_quarantine(
    existing: List[Dict[str, Any]],
    incoming: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {}
    for item in list(existing or []) + list(incoming or []):
        key = (int(item.get("game_type", 0)), (item.get("code") or "").strip().upper())
        if not key[1]:
            continue
        merged[key] = item
    return list(merged.values())


def should_notify_review(item: Dict[str, Any], now: datetime) -> bool:
    last_notified = parse_iso_datetime(item.get("last_notified_at"))
    if last_notified is not None and (now - last_notified) < timedelta(days=7):
        return False
    if item.get("source_url"):
        return True
    description = (
        (item.get("rewards_description_ru") or "")
        + " "
        + (item.get("rewards_description_en") or "")
    )
    if any(ch.isdigit() for ch in description):
        return True
    return str(item.get("id", "")).startswith(("manual_", "verified_"))


def apply_official_verification(
    data: dict,
    quarantine_items: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    now_iso: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    published = {
        (int(code.get("game_type", 0)), (code.get("code") or "").strip().upper()): code
        for code in data.get("codes", [])
    }
    quarantine = {
        (int(code.get("game_type", 0)), (code.get("code") or "").strip().upper()): code
        for code in quarantine_items
    }

    verified_new: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []
    now = parse_iso_datetime(now_iso) or datetime.now(timezone.utc)

    for result in results or []:
        game_type = int(result.get("game_type", 0))
        code = (result.get("code") or "").strip().upper()
        if not code:
            continue
        key = (game_type, code)
        status = result.get("status")

        if status == "verified":
            item = published.get(key) or quarantine.pop(key, None)
            if item is None:
                item = {
                    "id": f"official_{game_type}_{code.lower()}",
                    "game_type": game_type,
                    "code": code,
                    "created_at": now_iso,
                    "is_stream": False,
                }
            item["rewards_description_ru"] = result.get("rewards_description_ru")
            item["rewards_description_en"] = result.get("rewards_description_en")
            item["reward_types"] = result.get("reward_types") or []
            item["verification_status"] = "verified"
            item["source_type"] = "official"
            item["source_url"] = result.get("source_url")
            item["source_id"] = result.get("source_id") or ""
            item["verified_at"] = now_iso
            item["expiry_confidence"] = result.get("expiry_confidence") or "unknown"
            if result.get("expires_at"):
                item["expires_at"] = result["expires_at"]
            else:
                item["expires_at"] = None
            item["status"] = "ACTIVE"
            item["is_active"] = True
            item.pop("quarantine_reason", None)
            item.pop("last_checked_at", None)
            item.pop("last_notified_at", None)
            published[key] = item
            verified_new.append(item)
            print(f"[OfficialCodes] Verified {code} ({game_type}) via {result.get('source_url')}")
            continue

        item = quarantine.get(key) or published.get(key)
        if item is None:
            item = {
                "id": f"official_{game_type}_{code.lower()}",
                "game_type": game_type,
                "code": code,
                "created_at": now_iso,
                "is_stream": False,
            }
        item["verification_status"] = "unverified"
        item["quarantine_reason"] = (
            "official_source_ambiguous"
            if status == "ambiguous"
            else "official_source_not_found"
        )
        item["last_checked_at"] = now_iso
        if result.get("source_url"):
            item["source_url"] = result["source_url"]
        if result.get("source_id"):
            item["source_id"] = result["source_id"]
        quarantine[key] = item
        if should_notify_review(item, now):
            item["last_notified_at"] = now_iso
            review.append(item)

    data["codes"] = list(published.values())
    return list(quarantine.values()), verified_new, review


def moderate_promocodes(data: dict) -> dict:
    now = datetime.now(timezone.utc)
    raw_codes = data.get("codes", [])
    print(f"Processing {len(raw_codes)} promocodes...")

    deduped = {}

    for item in raw_codes:
        raw_code = item.get("code", "").strip().upper()
        if not validate_code(raw_code):
            continue

        game_type = int(item.get("game_type", 0))
        key = (game_type, raw_code)

        item["code"] = raw_code
        item["game_type"] = game_type

        # 1. Protect permanent codes
        if key in PERMANENT_CODES:
            perm_meta = PERMANENT_CODES.get(key, {})
            item["status"] = "PERMANENT"
            item["is_stream"] = False
            item["is_active"] = True
            item["expires_at"] = None
            if not item.get("rewards_description_ru") and "rewards_description_ru" in perm_meta:
                item["rewards_description_ru"] = perm_meta["rewards_description_ru"]
            if not item.get("rewards_description_en") and "rewards_description_en" in perm_meta:
                item["rewards_description_en"] = perm_meta["rewards_description_en"]
            deduped[key] = item
            continue

        # 2. Identify livestream codes
        is_stream = bool(
            item.get("is_stream", False)
            or item.get("status") == "STREAM"
            or "stream" in str(item.get("id", "")).lower()
        )
        item["is_stream"] = is_stream

        expires_at_dt = parse_iso_datetime(item.get("expires_at"))
        created_at_dt = parse_iso_datetime(item.get("created_at"))

        if item.get("verification_status") == "verified":
            if not item.get("status"):
                item["status"] = "ACTIVE"
            if expires_at_dt is not None and now > expires_at_dt:
                item["is_active"] = False
                item["status"] = "EXPIRED"
            else:
                item["is_active"] = item.get("status") != "EXPIRED"
            deduped[key] = item
            continue

        # 3. Check expiration
        is_expired = False
        if is_stream:
            # Stream codes invariant: only valid for <= 28 hours from broadcast/creation
            if created_at_dt is not None and (now - created_at_dt) > timedelta(hours=28):
                is_expired = True
            elif expires_at_dt is not None and now > expires_at_dt:
                is_expired = True
            elif created_at_dt is None and expires_at_dt is None:
                is_expired = True
        else:
            # Regular codes
            if expires_at_dt is not None and now > expires_at_dt:
                is_expired = True
            elif created_at_dt is not None and (now - created_at_dt).days >= 45:
                # If discovered over 45 days ago without explicit verified future expiry
                if expires_at_dt is not None and expires_at_dt > now and (expires_at_dt - created_at_dt).days <= 65:
                    pass
                else:
                    is_expired = True

        was_active = item.get("is_active", True)

        if is_expired:
            item["is_active"] = False
            item["status"] = "EXPIRED"
        else:
            item["is_active"] = True
            if is_stream:
                item["status"] = "STREAM"
            elif item.get("status") == "NEW":
                if created_at_dt is not None and (now - created_at_dt) > timedelta(days=7):
                    item["status"] = "ACTIVE"
            elif not item.get("status") or (item.get("status") == "EXPIRED" and was_active):
                item["status"] = "ACTIVE"
            if item.get("status") == "EXPIRED":
                item["is_active"] = False

        deduped[key] = item

    active_codes = []
    expired_codes = []

    for item in deduped.values():
        if item.get("is_active", True) and item.get("status") != "EXPIRED":
            active_codes.append(item)
        else:
            expired_codes.append(item)

    def active_sort_key(x):
        # Category priority:
        # 0: Live Stream (urgent countdown) -> sorted by expires_at ASC
        # 1: New codes (created <= 7 days ago) -> sorted by created_at DESC (newest first)
        # 2: General active codes -> sorted by created_at DESC (newest first)
        # 3: Permanent codes -> sorted by code at end
        is_stream = bool(x.get("is_stream") or x.get("status") == "STREAM")
        is_perm = (x.get("status") == "PERMANENT")
        c_dt = parse_iso_datetime(x.get("created_at"))
        c_ts = c_dt.timestamp() if c_dt else 0.0

        if is_stream:
            cat = 0
            e_dt = parse_iso_datetime(x.get("expires_at"))
            sub_sort = e_dt.timestamp() if e_dt else (c_ts + 86400)
        elif is_perm:
            cat = 3
            sub_sort = x.get("code", "")
        elif c_dt and (now - c_dt).days <= 7:
            cat = 1
            sub_sort = -c_ts
        else:
            cat = 2
            sub_sort = -c_ts

        return (x.get("game_type", 0), cat, sub_sort)

    active_codes.sort(key=active_sort_key)

    def expired_sort_key(x):
        dt = parse_iso_datetime(x.get("expires_at")) or parse_iso_datetime(x.get("created_at"))
        return dt.timestamp() if dt else 0.0

    expired_codes.sort(key=expired_sort_key, reverse=True)

    pruned_expired = []
    counts_by_game = {}
    for item in expired_codes:
        if item.get("verification_status") == "verified":
            pruned_expired.append(item)
            continue
        g = item.get("game_type", 0)
        c = counts_by_game.get(g, 0)
        if c < 20:
            pruned_expired.append(item)
            counts_by_game[g] = c + 1

    final_list = active_codes + pruned_expired
    return {
        "schema_version": data.get("schema_version", 1),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "codes": final_list
    }


def import_scraped_banners(data: dict, scraped_banners: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges parsed official banners into the schedule using version/phase upsert."""
    if not scraped_banners:
        return []

    games = data.setdefault("games", [])
    game_dict = {}
    for g in games:
        game_dict[g.get("game_type", 0)] = g

    touched = []

    for b in scraped_banners:
        gt = b.get("game_type", 0)
        payload = {k: v for k, v in b.items() if k != "game_type"}
        if gt not in game_dict:
            new_g = {"game_type": gt, "banners": []}
            games.append(new_g)
            game_dict[gt] = new_g

        existing_banners = game_dict[gt].setdefault("banners", [])
        match = None
        for ex in existing_banners:
            if (ex.get("version") == payload.get("version")
                    and int(ex.get("phase", 0)) == int(payload.get("phase", 0))
                    and (ex.get("type") or "CHARACTER").upper() == (payload.get("type") or "CHARACTER").upper()):
                match = ex
                break

        if match is None:
            existing_banners.append(payload)
            touched.append(b)
            continue

        changed = False
        pairs = [
            ("featured_five_stars_ru", "featured_five_stars_en"),
            ("featured_four_stars_ru", "featured_four_stars_en"),
        ]
        if b.get("verification_status") == "verified":
            for key in (
                "start_date", "end_date", "source_url", "source_id",
                "source_type", "verification_status",
            ):
                value = b.get(key)
                if value is not None and match.get(key) != value:
                    match[key] = value
                    changed = True
            if changed and b.get("verified_at"):
                match["verified_at"] = b["verified_at"]
            for ru_key, en_key in pairs:
                new_ru = b.get(ru_key) or []
                new_en = b.get(en_key) or []
                if new_ru and match.get(ru_key) != new_ru:
                    match[ru_key] = new_ru
                    changed = True
                if new_en and match.get(en_key) != new_en:
                    match[en_key] = new_en
                    changed = True
        else:
            for ru_key, en_key in pairs:
                ru_list = match.setdefault(ru_key, [])
                en_list = match.setdefault(en_key, [])
                for ru, en in zip(b.get(ru_key, []), b.get(en_key, [])):
                    if ru not in ru_list:
                        ru_list.append(ru)
                        changed = True
                    if en not in en_list:
                        en_list.append(en)
                        changed = True

            if b.get("source_url") and not match.get("source_url"):
                match["source_url"] = b["source_url"]
                changed = True

        if changed:
            touched.append({**match, "game_type": gt})

    for g in games:
        g["banners"] = sorted(
            g.get("banners", []),
            key=lambda x: (
                x.get("start_date", ""),
                0 if (x.get("type") or "CHARACTER").upper() == "CHARACTER" else 1,
                x.get("phase", 1),
                x.get("id", "")
            )
        )

    if touched:
        print(f"Merged {len(touched)} official banner updates.")
    return touched


def moderate_banners(data: dict) -> dict:
    today = datetime.now(timezone.utc).date()
    games = data.get("games", [])
    total_banners = 0
    updated_statuses = 0

    for game in games:
        banners = game.get("banners", [])
        for banner in banners:
            total_banners += 1
            start = parse_date(banner.get("start_date"))
            end = parse_date(banner.get("end_date"))
            if not start or not end:
                continue

            old_status = banner.get("status", "")
            if start <= today <= end:
                new_status = "CURRENT"
            elif today > end:
                new_status = "EXPIRED"
            else:
                new_status = "ANNOUNCED"

            if old_status != new_status:
                banner["status"] = new_status
                updated_statuses += 1

    print(f"Banners schedule: checked {total_banners} banners, updated {updated_statuses} statuses.")
    return data


def quarantine_unverified_codes(data: dict) -> List[Dict[str, Any]]:
    kept = []
    pending = []
    for code in data.get("codes", []):
        status = (code.get("status") or "").upper()
        verified = code.get("verification_status") == "verified"
        if status in ("ACTIVE", "STREAM", "NEW") and not verified:
            pending.append({
                **code,
                "quarantine_reason": "official_source_required",
            })
            continue
        kept.append(code)
    data["codes"] = kept
    return pending


def merge_official_patches(data: dict, patches: Dict[int, Dict[str, Dict[str, str]]]) -> bool:
    games = data.setdefault("games", [])
    game_dict = {g.get("game_type", 0): g for g in games}
    changed = False
    for game_type, version_map in (patches or {}).items():
        game = game_dict.get(int(game_type))
        if not game:
            continue
        existing = {patch.get("version"): patch for patch in game.setdefault("patches", [])}
        for version, dates in version_map.items():
            patch = existing.get(version)
            if patch is None:
                patch = {"version": version, "title": "", **dates}
                game["patches"].append(patch)
                changed = True
            else:
                for key in ("start_date", "end_date"):
                    value = dates.get(key)
                    if value and patch.get(key) != value:
                        patch[key] = value
                        changed = True
        game["patches"].sort(key=lambda item: item.get("start_date", ""), reverse=True)
    return changed


def quarantine_unverified_banners(data: dict) -> List[Dict[str, Any]]:
    pending = []
    for game in data.get("games", []):
        kept = []
        for banner in game.get("banners", []):
            status = (banner.get("status") or "").upper()
            verified = banner.get("verification_status") == "verified"
            if status in ("CURRENT", "ANNOUNCED") and not verified:
                pending.append({
                    **banner,
                    "game_type": game.get("game_type", 0),
                    "quarantine_reason": "official_source_required",
                })
                continue
            if status == "EXPIRED" and not banner.get("verification_status"):
                banner["verification_status"] = "legacy"
            kept.append(banner)
        game["banners"] = kept
    return pending


def save_pending_banners(
    base_dir: str,
    pending: List[Dict[str, Any]],
    published_keys: Optional[set] = None,
):
    path = os.path.join(base_dir, "pending_banners.json")
    merged = {}
    if os.path.exists(path):
        existing = load_json(path, {"banners": []})
        for item in existing.get("banners", []):
            merged[(item.get("game_type", 0), item.get("id", ""))] = item
    for item in pending:
        merged[(item.get("game_type", 0), item.get("id", ""))] = item
    for key in published_keys or set():
        merged.pop(key, None)
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "banners": list(merged.values()),
    }
    if os.path.exists(path):
        existing = load_json(path, {})
        if without_timestamp(existing) == without_timestamp(payload):
            print(f"No changes for {path}")
            return
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(tmp_path, path)
    print(f"Quarantined {len(pending)} unverified banners to {path}")


def save_quarantined_codes(base_dir: str, pending: List[Dict[str, Any]]):
    path = os.path.join(base_dir, "quarantine_codes.json")
    merged = {}
    if os.path.exists(path):
        existing = load_json(path, {"codes": []})
        for item in existing.get("codes", []):
            merged[(item.get("game_type", 0), item.get("code", ""))] = item
    for item in pending:
        merged[(item.get("game_type", 0), item.get("code", ""))] = item
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "codes": list(merged.values()),
    }
    if os.path.exists(path):
        existing = load_json(path, {})
        if without_timestamp(existing) == without_timestamp(payload):
            print(f"No changes for {path}")
            return
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(tmp_path, path)
    print(f"Saved {len(merged)} quarantined code candidates to {path}")


def main():
    parser = argparse.ArgumentParser(description="GachaPoint Data Hub Sync")
    parser.add_argument("--add-code", nargs=4, metavar=("GAME_TYPE", "CODE", "REWARDS", "STATUS"),
                        help="Add new promo code: --add-code 0 PJ2KEBRAYSRM '60 Primogems' ACTIVE")
    parser.add_argument("--stream", action="store_true", help="Flag code as livestream reward")
    parser.add_argument("--no-scrape", action="store_true", help="Skip web scraping step")
    parser.add_argument("--no-verify", action="store_true", help="Skip official promo-code verification")
    args = parser.parse_args()

    base_dir = ROOT_DIR
    promocodes_file = os.path.join(base_dir, "promocodes.json")
    banners_file = os.path.join(base_dir, "banners_schedule.json")
    pending_file = os.path.join(base_dir, "pending_codes.json")

    try:
        promo_data = load_json(promocodes_file, {"schema_version": 1, "codes": []})
        all_new_codes = []
        quarantined_codes = []

        # 1. Automated scraping from Fandom MediaWiki
        if not args.no_scrape:
            try:
                print("Running automated web scraping for Genshin, HSR and ZZZ...")
                scraped = parse_all_games()
                new_scraped, quarantined_codes = import_scraped_codes(promo_data, scraped)
                all_new_codes.extend(new_scraped)
            except Exception as e:
                print(f"[Warning] Automated scraper encountered non-fatal error: {e}")

        # 2. Auto-import from pending_codes.json queue
        _, pending_added = import_pending_codes(promo_data, pending_file)
        all_new_codes.extend(pending_added)

        # 3. Manual addition via CLI
        if args.add_code:
            g_type = int(args.add_code[0])
            raw_code = args.add_code[1].strip().upper()
            rewards = args.add_code[2]
            status = args.add_code[3].upper()
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            new_entry = {
                "id": f"manual_{g_type}_{raw_code.lower()}",
                "game_type": g_type,
                "code": raw_code,
                "rewards_description_ru": rewards,
                "rewards_description_en": rewards,
                "reward_types": ["PRIMOGEM"] if g_type == 0 else ["JADE"] if g_type == 1 else ["POLYCHROME"] if g_type == 2 else ["CRYSTAL"],
                "status": "STREAM" if args.stream else status,
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ") if args.stream else None,
                "created_at": now_iso,
                "is_stream": args.stream,
                "is_active": True
            }
            promo_data.setdefault("codes", []).append(new_entry)
            all_new_codes.append(new_entry)
            print(f"Manually added code {raw_code} for game {g_type}")

        # 4. Official-source verification for discovered and quarantined codes
        existing_quarantine = load_json(
            os.path.join(base_dir, "quarantine_codes.json"),
            {"schema_version": 1, "codes": []},
        ).get("codes", [])
        quarantined_codes = merge_quarantine(existing_quarantine, quarantined_codes)

        if not args.no_verify:
            candidates = [
                code for code in promo_data.get("codes", [])
                if (code.get("status") or "").upper() in ("ACTIVE", "STREAM", "NEW")
                and code.get("verification_status") != "verified"
            ]
            candidates.extend(quarantined_codes)
            try:
                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                results = verify_candidates(candidates)
                quarantined_codes, verified_by_official, review_items = apply_official_verification(
                    promo_data, quarantined_codes, results, now_iso
                )
                all_new_codes.extend(verified_by_official)
                if review_items:
                    notify_code_review(review_items)
            except Exception as e:
                print(f"[Warning] Official code verification encountered an error: {e}")

        # 5. Moderation & deduplication
        promo_data = moderate_promocodes(promo_data)
        quarantined_codes.extend(quarantine_unverified_codes(promo_data))
        quarantined_codes = merge_quarantine([], quarantined_codes)
        save_json(promocodes_file, promo_data)
        save_quarantined_codes(base_dir, quarantined_codes)

        # 6. Banner announcements scraping & calendar moderation
        if os.path.exists(banners_file):
            banner_data = load_json(banners_file, {"schema_version": 1, "games": []})
            newly_added_banners = []

            if not args.no_scrape:
                try:
                    catalog_file = os.path.join(base_dir, "game_catalog.json")
                    print("Running automated official data scraping...")
                    official_data = parse_all_official_data(catalog_file)
                    if official_data.get("errors"):
                        print(
                            f"[Warning] Some official banner parsers failed: {official_data['errors']}",
                            file=sys.stderr,
                        )
                    newly_added_banners = import_scraped_banners(
                        banner_data, official_data.get("banners", [])
                    )
                    merge_official_patches(banner_data, official_data.get("patches", {}))
                except Exception as e:
                    print(f"[Warning] Official banner parser failed: {e}", file=sys.stderr)

            banner_data = moderate_banners(banner_data)
            pending_banners = quarantine_unverified_banners(banner_data)
            published_keys = {
                (game.get("game_type", 0), banner.get("id", ""))
                for game in banner_data.get("games", [])
                for banner in game.get("banners", [])
                if banner.get("verification_status") == "verified"
            }
            save_pending_banners(base_dir, pending_banners, published_keys)
            save_json(banners_file, banner_data)

            if newly_added_banners:
                notify_new_banners(newly_added_banners)

        # 7. Telegram notification on new codes
        if all_new_codes:
            notify_new_codes(all_new_codes)

        print("Sync completed successfully.")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CRITICAL ERROR] Sync failed: {e}\n{tb}", file=sys.stderr)
        notify_failure("Data Hub Sync Failed", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
