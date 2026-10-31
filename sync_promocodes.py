#!/usr/bin/env python3
"""
GachaPoint Data Hub — Autonomous Validation, Moderation & Sync Script

Provides automated data maintenance:
1. Auto-import new promo codes from pending_codes.json or CLI.
2. Maintain strict categorization: PERMANENT, STREAM, ACTIVE, EXPIRED.
3. Banner schedule moderation with calendar-based status updates.
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timezone, timedelta

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


def save_json(filepath: str, data: dict):
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {filepath} (updated_at: {data['updated_at']})")


def import_pending_codes(data: dict, pending_file: str = "pending_codes.json") -> int:
    """Автоматически подхватывает новые промокоды из буферного файла pending_codes.json без ручного вмешательства."""
    if not os.path.exists(pending_file):
        return 0

    pending = load_json(pending_file, {})
    new_items = pending.get("codes", []) if isinstance(pending, dict) else pending
    if not isinstance(new_items, list) or not new_items:
        return 0

    existing_codes = {(c.get("game_type", 0), c.get("code", "").strip().upper()) for c in data.get("codes", [])}
    added_count = 0
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
        added_count += 1

    # Clean up pending queue
    try:
        os.remove(pending_file)
        print(f"Imported {added_count} new codes from {pending_file} and cleared pending queue.")
    except Exception as e:
        print(f"Warning: could not remove {pending_file}: {e}")

    return added_count


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
        is_stream = bool(item.get("is_stream", False)) or item.get("status") == "STREAM" or "stream" in str(item.get("id", "")).lower()
        item["is_stream"] = is_stream

        expires_at_dt = parse_iso_datetime(item.get("expires_at"))
        created_at_dt = parse_iso_datetime(item.get("created_at"))

        # 3. Check expiration
        is_expired = False
        if expires_at_dt is not None:
            if now > expires_at_dt:
                is_expired = True
        elif is_stream:
            # Livestream codes expire within 16-24 hours
            if created_at_dt is not None and (now - created_at_dt) > timedelta(hours=20):
                is_expired = True
            elif created_at_dt is None:
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

    # 4. Separate active and expired codes
    active_codes = []
    expired_codes = []

    for item in deduped.values():
        if item.get("is_active", True) and item.get("status") != "EXPIRED":
            active_codes.append(item)
        else:
            expired_codes.append(item)

    def active_sort_key(x):
        is_stream = 0 if (x.get("is_stream") or x.get("status") == "STREAM") else 1
        is_perm = 2 if x.get("status") == "PERMANENT" else 0
        return (x.get("game_type", 0), is_perm, is_stream, x.get("code", ""))

    active_codes.sort(key=active_sort_key)

    # Sort expired by expiration/creation date and prune to limit
    expired_codes.sort(key=lambda x: x.get("expires_at") or x.get("created_at") or "", reverse=True)
    pruned_expired = []
    counts_by_game = {}
    for item in expired_codes:
        g = item.get("game_type", 0)
        c = counts_by_game.get(g, 0)
        if c < 15:
            pruned_expired.append(item)
            counts_by_game[g] = c + 1

    final_list = active_codes + pruned_expired
    print(f"Moderation summary: {len(active_codes)} active codes, {len(pruned_expired)} archived expired codes.")
    data["codes"] = final_list
    return data


def moderate_banners(data: dict) -> dict:
    today = datetime.now(timezone.utc).date()
    games = data.get("games", [])
    total_banners = 0
    updated_statuses = 0

    for game in games:
        for banner in game.get("banners", []):
            total_banners += 1
            start = parse_date(banner.get("start_date"))
            end = parse_date(banner.get("end_date"))
            if not start or not end:
                continue

            old_status = banner.get("status")
            if today > end:
                new_status = "ENDED"
            elif start <= today <= end:
                new_status = "CURRENT"
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
    args = parser.parse_args()

    promocodes_file = "promocodes.json"
    banners_file = "banners_schedule.json"

    promo_data = load_json(promocodes_file, {"version": 1, "codes": []})

    # Auto-import from pending_codes.json queue
    import_pending_codes(promo_data)

    # Manual addition via CLI
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
        print(f"Manually added code {raw_code} for game {g_type}")

    promo_data = moderate_promocodes(promo_data)
    save_json(promocodes_file, promo_data)

    if os.path.exists(banners_file):
        banner_data = load_json(banners_file, {"version": 1, "games": []})
        banner_data = moderate_banners(banner_data)
        save_json(banners_file, banner_data)


if __name__ == "__main__":
    main()
