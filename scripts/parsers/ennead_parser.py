#!/usr/bin/env python3
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from scripts.parsers.fandom_parser import parse_rewards_from_text
from scripts.parsers.official_banners_parser import (
    auto_register_catalog_character,
    make_banner,
    resolve_item,
)

BASE_URL = "https://api.ennead.cc/mihoyo"
SLUGS = {0: "genshin", 1: "starrail", 2: "zenless", 3: "honkai"}


def fetch_json_safe(url: str, timeout: int = 10) -> Optional[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointDataHub/2.0",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == 1:
                return None
    return None


def parse_ennead_codes() -> List[Dict[str, Any]]:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []

    for game_type, slug in SLUGS.items():
        url = f"{BASE_URL}/{slug}/codes"
        data = fetch_json_safe(url, timeout=10)
        if not data or not isinstance(data, dict):
            continue

        active_codes = data.get("active", [])
        if not isinstance(active_codes, list):
            continue

        for item in active_codes:
            code = (item.get("code") or "").strip().upper()
            if not code or len(code) < 3 or code in ("YUANSHEN",):
                continue

            raw_rewards = item.get("rewards") or []
            combined_text = "; ".join(raw_rewards) if isinstance(raw_rewards, list) else str(raw_rewards)
            desc_ru, desc_en, reward_types = parse_rewards_from_text(combined_text, game_type)

            if not desc_ru:
                desc_ru = combined_text
            if not desc_en:
                desc_en = combined_text

            is_stream = "stream" in code.lower() or "stream" in combined_text.lower()

            results.append({
                "id": f"ennead_{game_type}_{code.lower()}",
                "game_type": game_type,
                "code": code,
                "rewards_description_ru": desc_ru,
                "rewards_description_en": desc_en,
                "reward_types": reward_types,
                "status": "STREAM" if is_stream else "ACTIVE",
                "expires_at": None,
                "expiry_confidence": "unknown",
                "created_at": now_iso,
                "source_url": url,
                "source_type": "trusted_api",
                "verification_status": "verified",
                "verified_at": now_iso,
                "is_stream": is_stream,
                "is_active": True,
            })

    return results


def _timestamp_to_date(ts: Any) -> Optional[str]:
    if not ts:
        return None
    try:
        val = int(ts)
        return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_ennead_banners(
    catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]],
    catalog_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    banners = []
    now = datetime.now(timezone.utc).date()

    existing_phases: Dict[Tuple[int, str, int], Tuple[str, str]] = {}
    if catalog_path and os.path.exists(catalog_path):
        base_dir = os.path.dirname(catalog_path)
        banners_path = os.path.join(base_dir, "banners_schedule.json")
        if os.path.exists(banners_path):
            try:
                with open(banners_path, "r", encoding="utf-8-sig") as bf:
                    bs_data = json.load(bf)
                for g in bs_data.get("games", []):
                    gt = int(g.get("game_type", 0))
                    for eb in g.get("banners", []):
                        ev = str(eb.get("version", ""))
                        ep = int(eb.get("phase", 0))
                        es = str(eb.get("start_date", ""))
                        ee = str(eb.get("end_date", ""))
                        if ev and ep and es and ee and (eb.get("type") or "CHARACTER").upper() == "CHARACTER":
                            existing_phases[(gt, ev, ep)] = (es, ee)
            except Exception:
                pass

    for game_type in (0, 1, 2):
        slug = SLUGS.get(game_type)
        if not slug:
            continue
        url = f"{BASE_URL}/{slug}/calendar"
        data = fetch_json_safe(url, timeout=10)
        if not data or not isinstance(data, dict):
            continue

        raw_banners = data.get("banners", [])
        if not isinstance(raw_banners, list):
            continue

        for b in raw_banners:
            version = str(b.get("version") or "")
            if not version:
                continue

            start_date = _timestamp_to_date(b.get("start_time"))
            end_date = _timestamp_to_date(b.get("end_time"))
            if not start_date or not end_date:
                continue

            characters = b.get("characters") or b.get("agents") or []
            if not characters:
                continue

            five_names = []
            four_names = []
            for c in characters:
                name = c.get("full_name") or c.get("name") or ""
                if not name:
                    continue
                resolved = resolve_item(name, catalog_lookup.get(game_type, {}))
                if resolved and resolved.get("type") and resolved.get("type") != "CHARACTER":
                    continue
                rarity = str(c.get("rarity") or "")
                if rarity in ("5", "5★", "S"):
                    if name not in five_names:
                        five_names.append(name)
                elif rarity in ("4", "4★", "A"):
                    if name not in four_names:
                        four_names.append(name)

            if not five_names:
                continue

            b_name = (b.get("name") or b.get("title") or "").lower()
            is_chronicled = (game_type == 0) and (
                "chronicled" in b_name
                or "хроник" in b_name
                or str(b.get("type", "")).upper() == "CHRONICLED"
                or "chronicled" in str(b.get("id", "")).lower()
                or len(five_names) >= 5
            )
            banner_type = "CHRONICLED" if is_chronicled else "CHARACTER"

            phase = 1
            if b.get("phase"):
                try:
                    phase = int(b.get("phase"))
                except Exception:
                    phase = 1
            else:
                matched_phase = None
                for (egt, ev, ep), (es, ee) in existing_phases.items():
                    if egt == game_type and ev == version:
                        if es == start_date or ee == end_date:
                            matched_phase = ep
                            break
                if matched_phase is not None:
                    phase = matched_phase
                else:
                    prev = [
                        ep for (egt, ev, ep), (es, ee) in existing_phases.items()
                        if egt == game_type and ev == version and ee <= start_date
                    ]
                    phase = (max(prev) + 1) if prev else 1

            banner_id = (
                f"genshin_{version.replace('.', '_')}_chronicled"
                if (game_type == 0 and is_chronicled)
                else str(b.get("id") or f"ennead_{slug}_{version}_{phase}")
            )

            banner_obj = make_banner(
                game_type,
                version,
                phase,
                start_date,
                end_date,
                five_names,
                four_names,
                url,
                banner_id,
                catalog_lookup,
                catalog_path=catalog_path,
                banner_type=banner_type,
                source_type="trusted_api",
                verification_status="verified",
            )
            if banner_obj:
                banners.append(banner_obj)

    return banners
