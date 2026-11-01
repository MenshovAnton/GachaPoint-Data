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
from typing import List, Dict, Any, Tuple

# Safe imports for alerts and parsers
try:
    from notify import notify_failure, notify_new_codes, notify_new_banners, notify_suspicious_announcement
except ImportError:
    def notify_failure(summary, details=None):
        print(f"[Alert] Failure: {summary} - {details}")
    def notify_new_codes(new_codes):
        print(f"[Alert] New codes found: {len(new_codes)}")
    def notify_new_banners(new_banners):
        print(f"[Alert] New banners found: {len(new_banners)}")
    def notify_suspicious_announcement(game_name, title, reason, post_url=None):
        print(f"[Alert] Suspicious announcement in {game_name}: {title} ({reason})")

try:
    from parsers.fandom_parser import parse_all_games
except ImportError:
    def parse_all_games():
        return []

try:
    from parsers.official_banners_parser import parse_all_official_banners
except ImportError:
    def parse_all_official_banners(catalog_path):
        return []

CODE_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,30}$")

PERMANENT_CODES = {
    (0, "GENSHINGIFT"): {
        "rewards_description": "50 Камней Истока, 3 Опыта героя",
        "rewards_description_ru": "50 Камней Истока, 3 Опыта героя",
        "rewards_description_en": "50 Primogems, 3 Hero's Wit",
        "reward_types": ["PRIMOGEM", "EXP"]
    },
    (1, "STARRAILGIFT"): {
        "rewards_description": "50 Звёздного нефрита, 2 Путеводителя, 10 000 Кредитов",
        "rewards_description_ru": "50 Звёздного нефрита, 2 Путеводителя, 10 000 Кредитов",
        "rewards_description_en": "50 Stellar Jade, 2 Traveler's Guide, 10,000 Credits",
        "reward_types": ["JADE", "EXP", "CREDIT"]
    },
    (2, "ZENLESSGIFT"): {
        "rewards_description": "50 Полихромов, 2 Журнала специалиста, 3 Источника питания",
        "rewards_description_ru": "50 Полихромов, 2 Журнала специалиста, 3 Источника питания",
        "rewards_description_en": "50 Polychromes, 2 Official Investigator Logs, 3 W-Engine Power Supplies",
        "reward_types": ["POLYCHROME", "EXP"]
    },
    (2, "ZZZTVCM"): {
        "rewards_description": "50 Полихромов, 1 Бустер",
        "rewards_description_ru": "50 Полихромов, 1 Бустер",
        "rewards_description_en": "50 Polychromes, 1 Booster",
        "reward_types": ["POLYCHROME"]
    },
    (3, "HONKAIGIFT"): {
        "rewards_description": "30 Кристаллов, 2 000 Монет",
        "rewards_description_ru": "30 Кристаллов, 2 000 Монет",
        "rewards_description_en": "30 Crystals, 2,000 Coins",
        "reward_types": ["CRYSTAL"]
    },
    (1, "CREATIONNYMPH"): {
        "rewards_description": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (1, "FAREWELL"): {
        "rewards_description": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (1, "IFYOUAREREADINGTHIS"): {
        "rewards_description": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (1, "OMEGA"): {
        "rewards_description": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_ru": "60 Звёздного нефрита, 1 Топливо",
        "rewards_description_en": "60 Stellar Jade, 1 Fuel",
        "reward_types": ["JADE"]
    },
    (3, "CheersCaptain"): {
        "rewards_description": "100 Кристаллов",
        "rewards_description_ru": "100 Кристаллов",
        "rewards_description_en": "100 Crystals",
        "reward_types": ["CRYSTAL"]
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

    if "promocodes" in filepath or "codes" in data:
        codes = data.get("codes", [])
        if not codes or len(codes) < 4:
            raise ValueError(f"Safety abort: {filepath} code count ({len(codes)}) below minimum safe threshold")

        existing_perms = {(c.get("game_type"), c.get("code")) for c in codes if c.get("status") == "PERMANENT"}
        mandatory_perms = {
            (0, "GENSHINGIFT"),
            (1, "STARRAILGIFT"),
            (2, "ZENLESSGIFT"),
            (2, "ZZZTVCM"),
            (3, "HONKAIGIFT")
        }
        missing_perms = mandatory_perms - existing_perms
        if missing_perms:
            raise ValueError(f"Safety abort: {filepath} is missing mandatory permanent codes: {missing_perms}")


def save_json(filepath: str, data: dict):
    """Saves JSON atomically via temp file with validation."""
    validate_dataset_before_save(filepath, data)

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
        assets_target = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "data", filename)
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


def import_scraped_codes(data: dict, scraped_codes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges freshly scraped codes into dataset safely without sliding date corruption."""
    if not scraped_codes:
        return []

    existing_map = {(c.get("game_type", 0), c.get("code", "").strip().upper()): c for c in data.get("codes", [])}
    newly_added = []

    for item in scraped_codes:
        g_type = item.get("game_type", 0)
        code_str = item.get("code", "").strip().upper()
        if not validate_code(code_str):
            continue

        key = (g_type, code_str)
        if key in existing_map:
            existing_item = existing_map[key]
            # If scraper confirms code is expired, sync expired status
            if item.get("status") == "EXPIRED" or not item.get("is_active", True):
                existing_item["status"] = "EXPIRED"
                existing_item["is_active"] = False
                if item.get("expires_at") and not existing_item.get("expires_at"):
                    existing_item["expires_at"] = item["expires_at"]
            if item.get("is_stream"):
                existing_item["is_stream"] = True
            # DO NOT overwrite expires_at on active existing codes with synthetic dates!
            # Only fill in if existing_item had no expires_at
            if not existing_item.get("expires_at") and item.get("expires_at"):
                existing_item["expires_at"] = item["expires_at"]
            continue

        data.setdefault("codes", []).append(item)
        existing_map[key] = item
        newly_added.append(item)

    if newly_added:
        print(f"Merged {len(newly_added)} newly discovered promo codes from web scraper.")
    return newly_added


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
        if key in PERMANENT_CODES or item.get("status") == "PERMANENT":
            perm_meta = PERMANENT_CODES.get(key, {})
            item["status"] = "PERMANENT"
            item["is_stream"] = False
            item["is_active"] = True
            item["expires_at"] = None
            if not item.get("rewards_description") and "rewards_description" in perm_meta:
                item["rewards_description"] = perm_meta["rewards_description"]
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
            elif not item.get("status") or item.get("status") == "EXPIRED":
                item["status"] = "ACTIVE"

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
        g = item.get("game_type", 0)
        c = counts_by_game.get(g, 0)
        if c < 20:
            pruned_expired.append(item)
            counts_by_game[g] = c + 1

    final_list = active_codes + pruned_expired
    return {
        "version": data.get("version", 1),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "codes": final_list
    }


def import_scraped_banners(data: dict, scraped_banners: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges freshly parsed official banners safely into banners_schedule.json without duplicates."""
    if not scraped_banners:
        return []

    games = data.setdefault("games", [])
    game_dict = {}
    for g in games:
        game_dict[g.get("game_type", 0)] = g

    newly_added = []

    for b in scraped_banners:
        gt = b.get("game_type", 0)
        if gt not in game_dict:
            new_g = {"game_type": gt, "banners": []}
            games.append(new_g)
            game_dict[gt] = new_g

        existing_banners = game_dict[gt].setdefault("banners", [])
        existing_ids = {ex.get("id") for ex in existing_banners}
        # Also check existing versions and 5 stars to prevent duplicate phases
        existing_keys = {
            (ex.get("version"), ex.get("phase"), tuple(sorted(ex.get("featured_five_stars_en", []))))
            for ex in existing_banners
        }

        b_key = (b.get("version"), b.get("phase"), tuple(sorted(b.get("featured_five_stars_en", []))))

        if b.get("id") in existing_ids or b_key in existing_keys:
            continue

        existing_banners.insert(0, b)
        newly_added.append(b)

    if newly_added:
        print(f"Merged {len(newly_added)} newly discovered official banners.")
    return newly_added


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


def main():
    parser = argparse.ArgumentParser(description="GachaPoint Data Hub Sync")
    parser.add_argument("--add-code", nargs=4, metavar=("GAME_TYPE", "CODE", "REWARDS", "STATUS"),
                        help="Add new promo code: --add-code 0 PJ2KEBRAYSRM '60 Primogems' ACTIVE")
    parser.add_argument("--stream", action="store_true", help="Flag code as livestream reward")
    parser.add_argument("--no-scrape", action="store_true", help="Skip web scraping step")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    promocodes_file = os.path.join(base_dir, "promocodes.json")
    banners_file = os.path.join(base_dir, "banners_schedule.json")
    pending_file = os.path.join(base_dir, "pending_codes.json")

    try:
        promo_data = load_json(promocodes_file, {"version": 1, "codes": []})
        all_new_codes = []

        # 1. Automated scraping from Fandom MediaWiki
        if not args.no_scrape:
            try:
                print("Running automated web scraping for Genshin, HSR and ZZZ...")
                scraped = parse_all_games()
                new_scraped = import_scraped_codes(promo_data, scraped)
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
                "rewards_description": rewards,
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

        # 4. Moderation & deduplication
        promo_data = moderate_promocodes(promo_data)
        save_json(promocodes_file, promo_data)

        # 5. Banner announcements scraping & calendar moderation
        if os.path.exists(banners_file):
            banner_data = load_json(banners_file, {"version": 1, "games": []})
            newly_added_banners = []

            if not args.no_scrape:
                try:
                    catalog_file = os.path.join(base_dir, "game_catalog.json")
                    print("Running automated official banner scraping from HoYoLAB...")
                    scraped_banners = parse_all_official_banners(catalog_file)
                    newly_added_banners = import_scraped_banners(banner_data, scraped_banners)
                except Exception as e:
                    print(f"[Warning] Official banner parser encountered non-fatal error: {e}")

            banner_data = moderate_banners(banner_data)
            save_json(banners_file, banner_data)

            if newly_added_banners:
                notify_new_banners(newly_added_banners)

        # 6. Telegram notification on new codes
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
