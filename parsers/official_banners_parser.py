#!/usr/bin/env python3
"""
Official HoYoLAB News API Banner Parser for HoYoverse Games
Strictly official announcements only — zero leaks or speculative banners.
Cross-references all parsed entities with game_catalog.json and alerts via Telegram
on ambiguous entities requiring manual verification.
"""

import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional

try:
    from notify import notify_suspicious_announcement
except ImportError:
    try:
        from ..notify import notify_suspicious_announcement
    except ImportError:
        def notify_suspicious_announcement(game_name, title, reason, post_url=None):
            print(f"[Alert] Suspicious announcement in {game_name}: {title} ({reason})")

# HoYoLAB Game IDs (gids)
HOYOLAB_GAMES = {
    0: {"name": "Genshin Impact", "gid": 2, "wiki": "genshin-impact"},
    1: {"name": "Honkai: Star Rail", "gid": 6, "wiki": "honkai-star-rail"},
    2: {"name": "Zenless Zone Zero", "gid": 8, "wiki": "zenless-zone-zero"},
    3: {"name": "Honkai Impact 3rd", "gid": 1, "wiki": "honkaiimpact3"}
}

BANNER_KEYWORDS_RU = [
    "молитв", "прыжок", "повышена вероятность", "событие персонаж", "событие оружия",
    "выделенный канал", "сигнал события", "поставка"
]

BANNER_KEYWORDS_EN = [
    "event wish", "warp", "boosted drop rate", "character event", "weapon event",
    "signal search", "supply event"
]

DATE_RANGE_REGEXES = [
    # YYYY/MM/DD HH:mm(:ss) - YYYY/MM/DD HH:mm(:ss)
    re.compile(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:—|-|до|to|until)\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})", re.IGNORECASE),
    # After Version X.X update — YYYY/MM/DD
    re.compile(r"(?:после выхода|after(?: the)? version update).*?(?:—|-|до|to|until)\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})", re.IGNORECASE)
]

VERSION_REGEX = re.compile(r"(?:верси[ия]|version|v)\s*(\d+\.\d+)", re.IGNORECASE)


def normalize_date(raw_date: str) -> Optional[str]:
    """Converts various date string representations to YYYY-MM-DD."""
    if not raw_date:
        return None
    raw_date = raw_date.strip().replace("/", "-")
    parts = raw_date.split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            return None
    return None


def fetch_hoyolab_news(gid: int, lang: str = "ru-ru", page_size: int = 15) -> List[Dict[str, Any]]:
    """Fetches official news list from HoYoLAB API."""
    url = "https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList"
    params = {
        "gids": gid,
        "type": 2, # Activities / Events / Notices
        "page_size": page_size,
        "client_type": 4
    }
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointOfficialParser/2.0",
            "Accept": "application/json",
            "x-rpc-language": lang
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("retcode") == 0 and "data" in data and "list" in data["data"]:
                    return data["data"]["list"]
    except Exception as e:
        print(f"[HoYoLAB] Warning: failed to fetch news for gid {gid} ({lang}): {e}")
    return []


def load_catalog_lookup(catalog_path: str) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """Loads game_catalog.json and returns a lookup dictionary by name (both ru and en)."""
    lookup = {0: {}, 1: {}, 2: {}, 3: {}}
    if not os.path.exists(catalog_path):
        return lookup

    try:
        with open(catalog_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            for g in data.get("games", []):
                gt = int(g.get("game_type", 0))
                for item in g.get("items", []):
                    name_ru = item.get("name_ru", item.get("name", "")).strip().lower()
                    name_en = item.get("name_en", "").strip().lower()
                    if name_ru:
                        lookup[gt][name_ru] = item
                    if name_en:
                        lookup[gt][name_en] = item
                    for alias in item.get("aliases", []):
                        if alias:
                            lookup[gt][alias.strip().lower()] = item
    except Exception as e:
        print(f"[Parser] Error reading catalog {catalog_path}: {e}")

    return lookup


def extract_characters_from_post(
    subject: str,
    content: str,
    game_lookup: Dict[str, Dict[str, Any]]
) -> Tuple[List[str], List[str], List[str]]:
    """
    Extracts recognized 5★ and 4★ items from post text by matching against game_catalog.
    Returns (five_stars_ru, four_stars_ru, unrecognized_quoted_names).
    """
    found_fives = []
    found_fours = []
    text_to_search = f"{subject}\n{content}".lower()

    # Match against catalog
    for name_lower, item in game_lookup.items():
        if len(name_lower) < 3:
            continue
        # Use word boundary or quotes
        pattern = r"(?:«|\"|\b)" + re.escape(name_lower) + r"(?:»|\"|\b)"
        if re.search(pattern, text_to_search):
            official_name = item.get("name_ru", item.get("name", name_lower.title()))
            rarity = item.get("rarity", "")
            if "5" in rarity and official_name not in found_fives:
                found_fives.append(official_name)
            elif "4" in rarity and official_name not in found_fours:
                found_fours.append(official_name)

    # Detect quoted names in subject that might be newly announced characters
    quoted_pattern = re.compile(r"[«\"]([^«\"»\n\r]{2,30})[»\"]")
    unrecognized = []
    for match in quoted_pattern.finditer(subject):
        candidate = match.group(1).strip()
        candidate_l = candidate.lower()
        if candidate_l not in game_lookup and not any(kw in candidate_l for kw in ["молитв", "событи", "оружи", "прыжок", "wish", "warp"]):
            unrecognized.append(candidate)

    return found_fives, found_fours, unrecognized


def parse_hoyolab_post_banner(
    post_item: Dict[str, Any],
    game_type: int,
    catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """Analyzes a single HoYoLAB post and constructs a banner entry if applicable."""
    post = post_item.get("post", {})
    subject = post.get("subject", "").strip()
    content = post.get("content", "").strip()
    post_id = post.get("post_id", "")
    post_url = f"https://www.hoyolab.com/article/{post_id}" if post_id else ""

    # Check if this post is a banner announcement
    subj_lower = subject.lower()
    is_banner = any(kw in subj_lower for kw in BANNER_KEYWORDS_RU) or any(kw in subj_lower for kw in BANNER_KEYWORDS_EN)
    if not is_banner:
        return None

    # Version extraction
    ver_match = VERSION_REGEX.search(subject) or VERSION_REGEX.search(content[:300])
    version = ver_match.group(1) if ver_match else None

    # Date extraction
    start_date = None
    end_date = None
    for pattern in DATE_RANGE_REGEXES:
        m = pattern.search(content)
        if m:
            if m.lastindex == 2:
                start_date = normalize_date(m.group(1))
                end_date = normalize_date(m.group(2))
            elif m.lastindex == 1:
                end_date = normalize_date(m.group(1))
            break

    # Extract characters
    game_lookup = catalog_lookup.get(game_type, {})
    fives_ru, fours_ru, unrecognized = extract_characters_from_post(subject, content, game_lookup)

    # If unrecognized names were found or crucial data is missing, notify Telegram
    game_name = HOYOLAB_GAMES.get(game_type, {}).get("name", "Gacha")
    if unrecognized:
        notify_suspicious_announcement(
            game_name=game_name,
            title=subject,
            reason=f"Обнаружены нераспознанные персонажи/предметы: {', '.join(unrecognized)}. Возможно, новый персонаж ещё не внесён в game_catalog.json.",
            post_url=post_url
        )

    if not fives_ru:
        # If no 5★ recognized from catalog, skip auto-import to prevent garbage
        return None

    if not end_date:
        return None

    # Determine phase based on dates or keywords
    phase = 1
    if "фаза ii" in subj_lower or "фаза 2" in subj_lower or "phase 2" in subj_lower:
        phase = 2
    elif "втор" in subj_lower:
        phase = 2

    # Cover image
    image_list = post_item.get("image_list", [])
    banner_image_url = image_list[0].get("url") if image_list else None

    # Build English names from catalog
    fives_en = [game_lookup.get(n.lower(), {}).get("name_en", n) for n in fives_ru]
    fours_en = [game_lookup.get(n.lower(), {}).get("name_en", n) for n in fours_ru]

    clean_version = version or "1.0"
    banner_id = f"{HOYOLAB_GAMES[game_type]['wiki']}_{clean_version.replace('.', '_')}_{phase}_{fives_en[0].lower().replace(' ', '_')}"

    return {
        "id": banner_id,
        "game_type": game_type,
        "version": clean_version,
        "phase": phase,
        "start_date": start_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "end_date": end_date,
        "status": "ANNOUNCED",
        "featured_five_stars_ru": fives_ru,
        "featured_five_stars_en": fives_en,
        "featured_five_stars": fives_ru,
        "featured_four_stars_ru": fours_ru,
        "featured_four_stars_en": fours_en,
        "featured_four_stars": fours_ru,
        "banner_image_url": banner_image_url,
        "source_url": post_url
    }


def parse_all_official_banners(catalog_path: str) -> List[Dict[str, Any]]:
    """Fetches and parses official banner announcements across all 4 HoYoverse games."""
    catalog_lookup = load_catalog_lookup(catalog_path)
    discovered_banners = []

    for game_type, config in HOYOLAB_GAMES.items():
        gid = config["gid"]
        print(f"[HoYoLAB] Checking official news for {config['name']} (gid {gid})...")
        posts = fetch_hoyolab_news(gid=gid, lang="ru-ru", page_size=15)
        for post in posts:
            try:
                banner_data = parse_hoyolab_post_banner(post, game_type, catalog_lookup)
                if banner_data:
                    discovered_banners.append(banner_data)
            except Exception as e:
                print(f"[HoYoLAB] Error parsing post in {config['name']}: {e}")

    return discovered_banners


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cat_file = os.path.join(base_dir, "game_catalog.json")
    banners = parse_all_official_banners(cat_file)
    print(f"Discovered {len(banners)} official banners from HoYoLAB:")
    for b in banners:
        print(f" - [{b['game_type']}] v{b['version']} Ph.{b['phase']} 5★: {b['featured_five_stars_ru']} ({b['start_date']} — {b['end_date']})")
