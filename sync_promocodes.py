#!/usr/bin/env python3
"""
GachaPoint Data Hub — Automatic Validation, Moderation & Sync Script
Поддерживает актуальность promocodes.json и banners_schedule.json:
- Жесткая модерация истекших кодов (по expires_at и лимитам стримов 16ч)
- Снятие статуса "NEW" у старых кодов (старше 7 дней -> ACTIVE)
- Автоматическое обновление статусов баннеров (CURRENT / ENDED / ANNOUNCED) по текущей дате
- Безопасное слияние с открытыми источниками сообщества
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta

CODE_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,30}$")

PERMANENT_CODES = {
    (0, "GENSHINGIFT"),
    (1, "STARRAILGIFT"),
    (2, "ZENLESSGIFT"),
    (2, "ZZZTVCM"),
}

COMMUNITY_SOURCES = [
    # Зеркала проверенных комьюнити-кодов
    "https://raw.githubusercontent.com/menshovanton/GachaPoint-Data/main/promocodes.json"
]


def validate_code(code: str) -> bool:
    if not code:
        return False
    return bool(CODE_REGEX.match(code.strip()))


def parse_iso_datetime(dt_str: str):
    if not dt_str:
        return None
    try:
        # ISO-8601 UTC
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
        with open(filepath, "r", encoding="utf-8") as f:
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

        # 1. Постоянные коды
        is_permanent = key in PERMANENT_CODES or item.get("status") == "PERMANENT"
        if is_permanent:
            item["status"] = "PERMANENT"
            item["is_stream"] = False
            item["is_active"] = True
            deduped[key] = item
            continue

        # 2. Проверка даты истечения expires_at
        expires_at_dt = parse_iso_datetime(item.get("expires_at"))
        created_at_dt = parse_iso_datetime(item.get("created_at"))

        is_stream = bool(item.get("is_stream", False)) or item.get("status") == "STREAM"
        
        # Исправление ложных стрим-тегов: обычные 50/60 гемов коды не являются стримовыми
        rewards_desc = item.get("rewards_description", "") + item.get("rewards_description_ru", "")
        if is_stream and ("60" in rewards_desc or "40" in rewards_desc or "30" in rewards_desc) and "100" not in rewards_desc:
            is_stream = False
            item["is_stream"] = False
            if item.get("status") == "STREAM":
                item["status"] = "ACTIVE"

        is_expired = False

        if expires_at_dt is not None:
            if now > expires_at_dt:
                is_expired = True
        elif is_stream:
            # Стримовые коды без явной даты живут максимум 16 часов с момента добавления
            if created_at_dt is not None and (now - created_at_dt) > timedelta(hours=16):
                is_expired = True
            elif created_at_dt is None:
                is_expired = True
        elif created_at_dt is not None and (now - created_at_dt) > timedelta(days=35):
            # Временные коды без expires_at живут 35 дней (1 патч)
            is_expired = True

        if is_expired:
            item["is_active"] = False
            item["status"] = "EXPIRED"
        else:
            item["is_active"] = True
            # Снятие статуса "NEW" для кодов старше 7 дней
            if item.get("status") == "NEW":
                if created_at_dt is not None and (now - created_at_dt) > timedelta(days=7):
                    item["status"] = "ACTIVE"
            elif not item.get("status") or item.get("status") == "EXPIRED":
                item["status"] = "STREAM" if is_stream else "ACTIVE"

        deduped[key] = item

    # Финальная сортировка и отсечение мусора
    # Разделяем на активные и истёкшие
    active_codes = []
    expired_codes = []

    for item in deduped.values():
        if item.get("is_active", True) and item.get("status") != "EXPIRED":
            active_codes.append(item)
        else:
            expired_codes.append(item)

    # Активные сортируем: сначала стримовые, потом обычные, потом постоянные
    def active_sort_key(x):
        is_stream = 0 if x.get("is_stream") else 1
        is_perm = 2 if x.get("status") == "PERMANENT" else 0
        return (x.get("game_type", 0), is_perm, is_stream, x.get("code", ""))

    active_codes.sort(key=active_sort_key)

    # Истёкшие оставляем не более 10 на игру, чтобы не раздувать файл
    expired_codes.sort(key=lambda x: x.get("expires_at", "") or x.get("created_at", ""), reverse=True)
    pruned_expired = []
    counts_by_game = {}
    for item in expired_codes:
        g = item.get("game_type", 0)
        c = counts_by_game.get(g, 0)
        if c < 10:
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
    promocodes_file = "promocodes.json"
    banners_file = "banners_schedule.json"

    # 1. Модерация промокодов
    promo_data = load_json(promocodes_file, {"version": 3, "codes": []})
    promo_data = moderate_promocodes(promo_data)
    save_json(promocodes_file, promo_data)

    # 2. Модерация расписания баннеров
    if os.path.exists(banners_file):
        banner_data = load_json(banners_file, {"version": 3, "games": []})
        banner_data = moderate_banners(banner_data)
        save_json(banners_file, banner_data)


if __name__ == "__main__":
    main()
