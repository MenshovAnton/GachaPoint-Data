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
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

try:
    from notify import notify_suspicious_announcement
except ImportError:
    try:
        from ..notify import notify_suspicious_announcement
    except ImportError:
        def notify_suspicious_announcement(game_name, title, reason, post_url=None):
            print(f"[Alert] Suspicious announcement in {game_name}: {title} ({reason})")

HOYOLAB_GAMES = {
    0: {"name": "Genshin Impact", "gid": 2, "wiki": "genshin-impact"},
    1: {"name": "Honkai: Star Rail", "gid": 6, "wiki": "honkai-star-rail"},
    2: {"name": "Zenless Zone Zero", "gid": 8, "wiki": "zenless-zone-zero"},
    3: {"name": "Honkai Impact 3rd", "gid": 1, "wiki": "honkaiimpact3"}
}

BANNER_SUBJECT_MARKERS_RU = [
    "события молитв", "молитва версии", "молитвы версии",
]
BANNER_SUBJECT_MARKERS_EN = [
    "event wishes", "event warp", "signal search",
]

VERSION_RE = re.compile(r"(?:версии|version)\s*(\d+\.\d+)", re.IGNORECASE)
PHASE_RE = re.compile(r"(?:Выпуск|Phase)\s*(III|II|I)\b", re.IGNORECASE)
DATE_RANGE_RE = re.compile(
    r"(\d{4})/(\d{1,2})/(\d{1,2})\s+\d{1,2}:\d{2}\s*[-–—]\s*"
    r"(\d{4})/(\d{1,2})/(\d{1,2})"
)
AFTER_UPDATE_RE = re.compile(
    r"(?:После выхода обновления|After the Version Update).*?"
    r"(\d{4})/(\d{1,2})/(\d{1,2})\s+\d{1,2}:\d{2}",
    re.IGNORECASE | re.DOTALL
)
FIVE_RU_RE = re.compile(r"эксклюзивного персонажа\s*5★\s*«[^»]*»\s*([^()\n]{2,40}?)\s*\(")
FOUR_RU_RE = re.compile(r"персонажей\s*4★\s*((?:«[^»]*»\s*[^,()\n]{2,40}\s*\([^)]*\)(?:\s*(?:,|и)\s*)?)+)")
FOUR_NAME_RU_RE = re.compile(r"«[^»]*»\s*([^,()\n]{2,40}?)\s*\(")
FIVE_EN_RE = re.compile(r"5-star character\s*\"[^\"]*\"\s*([^()\n]{2,40}?)\s*\(", re.IGNORECASE)
FOUR_EN_RE = re.compile(r"4-star characters?\s*((?:\"[^\"]*\"\s*[^,()\n]{2,40}\s*\([^)]*\)(?:\s*(?:,|and)\s*)?)+)", re.IGNORECASE)
FOUR_NAME_EN_RE = re.compile(r"\"[^\"]*\"\s*([^,()\n]{2,40}?)\s*\(")
TAG_RE = re.compile(r"<[^>]+>")


def fetch_hoyolab_news(gid: int, lang: str = "ru-ru", page_size: int = 30) -> List[Dict[str, Any]]:
    url = "https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList"
    params = {
        "gids": gid,
        "type": 3,
        "page_size": page_size,
        "client_type": 4
    }
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointOfficialParser/3.0",
            "Accept": "application/json",
            "x-rpc-language": lang
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("retcode") == 0 and "data" in data and "list" in data["data"]:
                    return data["data"]["list"]
    except Exception as e:
        print(f"[HoYoLAB] Warning: failed to fetch news for gid {gid} ({lang}): {e}")
    return []


def fetch_hoyolab_post_full(post_id: str, lang: str = "ru-ru") -> Optional[Dict[str, Any]]:
    url = "https://bbs-api-os.hoyolab.com/community/post/wapi/getPostFull"
    params = {"post_id": post_id}
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointOfficialParser/3.0",
            "Accept": "application/json",
            "x-rpc-language": lang
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("retcode") == 0:
                    post = data.get("data", {}).get("post", {}).get("post", {})
                    return post
    except Exception as e:
        print(f"[HoYoLAB] Warning: failed to fetch post {post_id}: {e}")
    return None


def load_catalog_lookup(catalog_path: str) -> Dict[int, Dict[str, Dict[str, Any]]]:
    lookup = {0: {}, 1: {}, 2: {}, 3: {}}
    if not os.path.exists(catalog_path):
        return lookup
    try:
        with open(catalog_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            for g in data.get("games", []):
                gt = int(g.get("game_type", 0))
                for item in g.get("items", []):
                    name_ru = item.get("name_ru", item.get("name", "")).strip().lower().replace("ё", "е")
                    name_en = item.get("name_en", "").strip().lower()
                    if name_ru:
                        lookup[gt][name_ru] = item
                    if name_en:
                        lookup[gt][name_en] = item
                    for alias in item.get("aliases", []):
                        if alias:
                            lookup[gt][alias.strip().lower().replace("ё", "е")] = item
    except Exception as e:
        print(f"[Parser] Error reading catalog {catalog_path}: {e}")
    return lookup


def load_patch_dates(banners_path: str) -> Dict[int, Dict[str, Dict[str, str]]]:
    result = {0: {}, 1: {}, 2: {}, 3: {}}
    if not os.path.exists(banners_path):
        return result
    try:
        with open(banners_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            for g in data.get("games", []):
                gt = int(g.get("game_type", 0))
                for patch in g.get("patches", []):
                    version = str(patch.get("version", "")).strip()
                    if version:
                        result[gt][version] = {
                            "start_date": patch.get("start_date", ""),
                            "end_date": patch.get("end_date", "")
                        }
    except Exception as e:
        print(f"[Parser] Error reading patches {banners_path}: {e}")
    return result


def normalize_date(y: str, m: str, d: str) -> Optional[str]:
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return None


def strip_html(content: str) -> str:
    return TAG_RE.sub(" ", content or "").replace("&nbsp;", " ")


def resolve_name(raw: str, game_lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    key = raw.strip().lower().replace("ё", "е")
    if key in game_lookup:
        return game_lookup[key]
    for alias, item in game_lookup.items():
        if len(alias) >= 3 and (key == alias or key in alias or alias in key):
            return item
    return None


def extract_names(content: str, game_lookup: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str], List[str]]:
    fives: List[str] = []
    fours: List[str] = []
    unresolved: List[str] = []

    for raw in FIVE_RU_RE.findall(content):
        item = resolve_name(raw, game_lookup)
        if item:
            name = item.get("name_ru") or item.get("name")
            if name not in fives:
                fives.append(name)
        else:
            unresolved.append(raw.strip())

    blocks = FOUR_RU_RE.findall(content)
    for block in blocks:
        for raw in FOUR_NAME_RU_RE.findall(block):
            item = resolve_name(raw, game_lookup)
            if item:
                name = item.get("name_ru") or item.get("name")
                if name not in fours:
                    fours.append(name)
            else:
                unresolved.append(raw.strip())

    if not fives:
        for raw in FIVE_EN_RE.findall(content):
            item = resolve_name(raw, game_lookup)
            if item:
                name = item.get("name_ru") or item.get("name")
                if name not in fives:
                    fives.append(name)
            else:
                unresolved.append(raw.strip())
    if not fours:
        for block in FOUR_EN_RE.findall(content):
            for raw in FOUR_NAME_EN_RE.findall(block):
                item = resolve_name(raw, game_lookup)
                if item:
                    name = item.get("name_ru") or item.get("name")
                    if name not in fours:
                        fours.append(name)
                else:
                    unresolved.append(raw.strip())

    return fives, fours, unresolved


def parse_hoyolab_post_banner(
    post_item: Dict[str, Any],
    game_type: int,
    catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]],
    patch_dates: Dict[int, Dict[str, Dict[str, str]]]
) -> Optional[Dict[str, Any]]:
    post = post_item.get("post", {})
    subject = (post.get("subject") or "").strip()
    content = strip_html(post.get("content") or "")
    subject_lower = subject.lower()

    is_banner = any(k in subject_lower for k in BANNER_SUBJECT_MARKERS_RU) or \
                any(k in subject_lower for k in BANNER_SUBJECT_MARKERS_EN)
    if not is_banner:
        return None

    if len(content) < 250:
        full_post = fetch_hoyolab_post_full(str(post.get("post_id", "")), "ru-ru")
        if full_post:
            content = strip_html(full_post.get("content") or content)

    version_match = VERSION_RE.search(subject) or VERSION_RE.search(content[:400])
    version = version_match.group(1) if version_match else None
    if not version:
        return None

    phase_match = PHASE_RE.search(subject)
    phase = 1
    if phase_match:
        phase = {"I": 1, "II": 2, "III": 3}.get(phase_match.group(1).upper(), 1)

    start_date = None
    end_date = None
    date_match = DATE_RANGE_RE.search(content)
    if date_match:
        start_date = normalize_date(date_match.group(1), date_match.group(2), date_match.group(3))
        end_date = normalize_date(date_match.group(4), date_match.group(5), date_match.group(6))
    else:
        after_match = AFTER_UPDATE_RE.search(content)
        if after_match:
            end_date = normalize_date(after_match.group(1), after_match.group(2), after_match.group(3))
            patch = patch_dates.get(game_type, {}).get(version, {})
            start_date = patch.get("start_date") or None

    if not start_date or not end_date:
        return None

    game_lookup = catalog_lookup.get(game_type, {})
    fives_ru, fours_ru, unresolved = extract_names(content, game_lookup)

    game_name = HOYOLAB_GAMES.get(game_type, {}).get("name", "Gacha")
    post_id = str(post.get("post_id", ""))
    post_url = f"https://www.hoyolab.com/article/{post_id}" if post_id else ""

    if unresolved:
        notify_suspicious_announcement(
            game_name=game_name,
            title=subject,
            reason=f"Нераспознанные сущности: {', '.join(unresolved[:8])}. Возможно, их нет в game_catalog.json.",
            post_url=post_url
        )

    if not fives_ru:
        return None

    fives_en = []
    fours_en = []
    for name in fives_ru:
        item = resolve_name(name, game_lookup)
        fives_en.append(item.get("name_en", name) if item else name)
    for name in fours_ru:
        item = resolve_name(name, game_lookup)
        fours_en.append(item.get("name_en", name) if item else name)

    slug = re.sub(r"[^a-z0-9]+", "_", fives_en[0].lower()).strip("_") if fives_en else "banner"
    banner_id = f"official_{HOYOLAB_GAMES[game_type]['wiki']}_{version.replace('.', '_')}_{phase}_{slug}"

    return {
        "id": banner_id,
        "game_type": game_type,
        "version": version,
        "phase": phase,
        "start_date": start_date,
        "end_date": end_date,
        "status": "ANNOUNCED",
        "featured_five_stars_ru": fives_ru,
        "featured_five_stars_en": fives_en,
        "featured_five_stars": fives_ru,
        "featured_four_stars_ru": fours_ru,
        "featured_four_stars_en": fours_en,
        "featured_four_stars": fours_ru,
        "source_url": post_url
    }


def parse_all_official_banners(catalog_path: str) -> List[Dict[str, Any]]:
    catalog_lookup = load_catalog_lookup(catalog_path)
    banners_path = os.path.join(os.path.dirname(catalog_path), "banners_schedule.json")
    patch_dates = load_patch_dates(banners_path)
    discovered_banners = []

    for game_type, config in HOYOLAB_GAMES.items():
        print(f"[HoYoLAB] Checking official news for {config['name']} (gid {config['gid']})...")
        posts = fetch_hoyolab_news(gid=config["gid"], lang="ru-ru", page_size=30)
        for post in posts:
            try:
                banner_data = parse_hoyolab_post_banner(post, game_type, catalog_lookup, patch_dates)
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
        print(json.dumps(b, ensure_ascii=False, indent=2))
