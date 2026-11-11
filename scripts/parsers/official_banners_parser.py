#!/usr/bin/env python3
"""
Official banner parser for HoYoverse games.

Sources:
- Genshin Impact: official in-game announcement API (Event Wish posts).
- Zenless Zone Zero: official website news API (Limited-Time Channels).
- Honkai Impact 3rd: official website news API (version update announcements).
- Honkai: Star Rail: official website news API (version update details).

Only data confirmed by these official sources is emitted. News that cannot be
resolved against the catalog is returned as a pending item instead of being
published.
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


GAME_NAMES = {
    0: "Genshin Impact",
    1: "Honkai: Star Rail",
    2: "Zenless Zone Zero",
    3: "Honkai Impact 3rd",
}

HOYOLAB_WIKI = {
    0: "genshin-impact",
    1: "honkai-star-rail",
    2: "zenless-zone-zero",
    3: "honkaiimpact3",
}

GENSHIN_ANN_URL = (
    "https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api/getAnnContent"
    "?game=hk4e&game_biz=hk4e_global&lang=en&bundle_id=hk4e_global"
    "&platform=pc&region=os_usa&level=60&uid=100000000"
)
GENSHIN_ANN_LIST_URL = (
    "https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api/getAnnList"
    "?game=hk4e&game_biz=hk4e_global&lang=en&bundle_id=hk4e_global"
    "&platform=pc&region=os_usa&level=60&uid=100000000"
)

CONTENT_API = "https://sg-public-api-static.hoyoverse.com/content_v2_user/app/{app}/getContentList"
CONTENT_DETAIL_API = "https://sg-public-api-static.hoyoverse.com/content_v2_user/app/{app}/getContent"

ZZZ_APP = "3e9196a4b9274bd7"
ZZZ_CHANNEL = "288"
ZZZ_SITE = "https://zenless.hoyoverse.com/en-us/news/detail/{id}"

HSR_APP = "113fe6d3b4514cdd"
HSR_CHANNEL = "250"
HSR_SITE = "https://hsr.hoyoverse.com/en-us/news/detail/{id}"
HSR_HOYOLAB_LIST = (
    "https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList"
    "?gids=6&type=1&page_size=50&client_type=4"
)
HSR_HOYOLAB_POST = "https://bbs-api-os.hoyolab.com/community/post/wapi/getPostFull"
HSR_ARTICLE = "https://www.hoyolab.com/article/{id}"

HI3_APP = "5fcd2aa439ca4aea"
HI3_CHANNEL = "514"
HI3_SITE = "https://honkaiimpact3.hoyoverse.com/global/en/news/detail/{id}"

GENSHIN_SITE = "https://genshin.hoyoverse.com/en/news"
GENSHIN_DETAIL = "https://genshin.hoyoverse.com/en/news/detail/{id}"

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
VERSION_RE = re.compile(r"(?:Version|версии)\s*(\d+\.\d+)", re.IGNORECASE)
GS_CHAR_RE = re.compile(
    r'"([^"]+)"\s+([A-Z][A-Za-z0-9\'. •-]+?)\s+\((Anemo|Geo|Electro|Dendro|Hydro|Pyro|Cryo)\)'
)
ZZZ_AGENT_RE = re.compile(r"limited S-Rank Agent\s+([A-Z][A-Za-z' -]+?)\s+\(", re.IGNORECASE)
HI3_SUIT_RE = re.compile(
    r"New (?:IMG-type )?S-rank Battlesuit\s+([A-Z][A-Za-z' -]{2,40}?)"
    r"(?=\s+(?:is|who|debuts|and|coming)\b|[.,(])",
    re.IGNORECASE,
)
HSR_FIVE_RE = re.compile(r"5-Star\s+([A-Z][A-Za-z' -]+?)\s+\(")
HSR_FIVE_EN_WARP_RE = re.compile(
    r'Character Event Warp,\s+the drop rates of the limited 5-star character\s+(.+?)\s*\([^)]+:[^)]+\)',
    re.IGNORECASE,
)
HSR_FIVE_EN_LIST_RE = re.compile(
    r"limited 5-star characters?\s+(.+?)(?=\s+and the limited 5-star Light Cone|\s+will (?:be boosted|return))",
    re.IGNORECASE,
)
HSR_FOUR_EN_BLOCK_RE = re.compile(
    r"4-star characters:?\s+(.+?)(?=,?\s+as well as|\s+will be boosted|\s+and 4-star Light Cones|\.)",
    re.IGNORECASE,
)
HSR_NAME_EN_RE = re.compile(r"([^,()]+?)\s*\([^)]+:[^)]+\)")
HSR_FIVE_RU_RE = re.compile(r"эксклюзивного персонажа\s+5★\s+([^(]+?)\s*\(", re.IGNORECASE)
HSR_FIVE_RU_LIST_RE = re.compile(
    r"эксклюзивных персонажей\s+5★\s+(.+?)(?=,\s+а также|\s+и\s+эксклюзив|\.)",
    re.IGNORECASE,
)
HSR_FOUR_RU_BLOCK_RE = re.compile(
    r"персонажей\s+4★:?\s*(.+?)(?=,?\s+а также|\s+и\s+Световых конусов|\s+Световых конусов|\.)",
    re.IGNORECASE,
)
HSR_NAME_RU_RE = re.compile(r"([А-ЯЁA-Z][^,()]+?)\s*\(")
HSR_DATE_RANGE_RE = re.compile(
    r"(?:с выхода версии\s+\d+\.\d+\s+)?"
    r"(\d{4}/\d{1,2}/\d{1,2})(?:\s+\d{1,2}:\d{2})?\s*(?:до|[-–—]|to)\s*"
    r"(\d{4}/\d{1,2}/\d{1,2})(?:\s+\d{1,2}:\d{2})?",
    re.IGNORECASE,
)
HSR_RU_DATE_RANGE_RE = re.compile(
    r"(\d{1,2}\s+[а-яё]+\s+\d{4})(?:\s+\d{1,2}:\d{2})?\s*(?:до|[-–—])\s*"
    r"(\d{1,2}\s+[а-яё]+\s+\d{4})(?:\s+\d{1,2}:\d{2})?",
    re.IGNORECASE,
)


def fetch_json(url: str, lang: Optional[str] = None, timeout: int = 40) -> Any:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointOfficialParser/4.0",
        "Accept": "application/json",
    }
    if lang:
        headers["x-rpc-language"] = lang
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise last_error or RuntimeError(f"Failed to fetch {url}")


def strip_html(value: str) -> str:
    unescaped = html.unescape(value or "")
    text = TAG_RE.sub(" ", unescaped)
    return re.sub(r"\s+", " ", text).strip()


def extract_hoyolab_text(post: Dict[str, Any]) -> str:
    raw = (post.get("content") or "").strip()
    if raw.lower() not in ("", "en-us", "ru-ru", "en", "ru"):
        cleaned = strip_html(raw)
        if len(cleaned) >= 40:
            return cleaned
    structured = post.get("structured_content")
    if structured:
        try:
            ops = json.loads(structured) if isinstance(structured, str) else structured
            if isinstance(ops, list):
                parts = [op["insert"] for op in ops if isinstance(op, dict) and isinstance(op.get("insert"), str)]
                joined = strip_html(" ".join(parts))
                if joined:
                    return joined
        except Exception:
            pass
    return strip_html(raw)


def normalize_name(value: str) -> str:
    text = (value or "").lower().replace("ё", "е")
    text = re.sub(r"[«»\"'’()`.,:;!?★•·\-–—]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_catalog_lookup(catalog_path: str) -> Dict[int, Dict[str, Dict[str, Any]]]:
    lookup = {0: {}, 1: {}, 2: {}, 3: {}}
    if not os.path.exists(catalog_path):
        return lookup
    with open(catalog_path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    for game in data.get("games", []):
        game_type = int(game.get("game_type", 0))
        for item in game.get("items", []):
            keys = [item.get("name_ru", ""), item.get("name_en", "")]
            keys.extend(item.get("aliases", []))
            for key in keys:
                if key:
                    lookup[game_type][normalize_name(key)] = item
    return lookup


def resolve_item(name: str, game_lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    key = normalize_name(name)
    if not key:
        return None
    if key in game_lookup:
        return game_lookup[key]
    candidates = []
    for alias, item in game_lookup.items():
        if len(key) >= 3 and (key in alias or alias in key):
            if item not in candidates:
                candidates.append(item)
    return candidates[0] if len(candidates) == 1 else None


def make_banner(
    game_type: int,
    version: str,
    phase: int,
    start_date: str,
    end_date: str,
    five_names: List[str],
    four_names: List[str],
    source_url: str,
    source_id: str,
    catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    game_lookup = catalog_lookup.get(game_type, {})
    five_ru: List[str] = []
    five_en: List[str] = []
    four_ru: List[str] = []
    four_en: List[str] = []

    for name in five_names:
        item = resolve_item(name, game_lookup)
        if not item:
            print(f"[OfficialParser] Unresolved 5-star '{name}' for {GAME_NAMES[game_type]}; banner skipped")
            return None
        five_ru.append(item.get("name_ru") or item.get("name_en") or name)
        five_en.append(item.get("name_en") or name)
    for name in four_names:
        item = resolve_item(name, game_lookup)
        if not item:
            print(f"[OfficialParser] Unresolved 4-star '{name}' for {GAME_NAMES[game_type]}; banner skipped")
            return None
        four_ru.append(item.get("name_ru") or item.get("name_en") or name)
        four_en.append(item.get("name_en") or name)

    if not five_ru:
        return None

    prefix = {0: "genshin", 1: "hsr", 2: "zzz", 3: "hi3"}[game_type]
    banner_id = f"{prefix}_{version.replace('.', '_')}_{phase}"

    return {
        "id": banner_id,
        "type": "CHARACTER",
        "game_type": game_type,
        "version": version,
        "phase": phase,
        "start_date": start_date,
        "end_date": end_date,
        "status": "ANNOUNCED",
        "featured_five_stars_ru": five_ru,
        "featured_five_stars_en": five_en,
        "featured_four_stars_ru": four_ru,
        "featured_four_stars_en": four_en,
        "source_url": source_url,
        "source_id": source_id,
        "source_type": "official",
        "verification_status": "verified",
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def parse_date(value: str) -> Optional[str]:
    match = DATE_RE.search(value or "")
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_month_day(month: str, day: str, year: int) -> Optional[str]:
    try:
        return datetime(year, MONTHS[month.upper()], int(day)).strftime("%Y-%m-%d")
    except (KeyError, ValueError):
        return None


def parse_ru_date(value: str) -> Optional[str]:
    match = re.search(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", (value or "").lower())
    if not match:
        return None
    day, month_name, year = match.groups()
    month = RU_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_genshin_dates(content: str, patch_start: str) -> Tuple[Optional[str], Optional[str]]:
    dates = DATE_RE.findall(content or "")
    if not dates:
        return None, None
    if re.search(r"After the Version\s+\d+\.\d+\s+update", content[:600], re.IGNORECASE) or len(dates) == 1:
        end_date = parse_date("/".join(dates[-1]))
        return (patch_start, end_date) if end_date else (None, None)
    start_date = parse_date("/".join(dates[0]))
    end_date = parse_date("/".join(dates[1]))
    return (start_date, end_date) if (start_date and end_date) else (None, None)


def parse_genshin_data(catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    payload = fetch_json(GENSHIN_ANN_URL, lang="en-us")
    announcements = payload.get("data", {}).get("list", [])
    list_payload = fetch_json(GENSHIN_ANN_LIST_URL, lang="en-us")
    metadata: Dict[int, Dict[str, Any]] = {}
    for group in list_payload.get("data", {}).get("list", []):
        for item in group.get("list", []):
            metadata[int(item.get("ann_id", 0))] = item

    patches: Dict[str, Dict[str, str]] = {}
    for item in metadata.values():
        title = item.get("title", "") or ""
        match = re.search(r"Version\s+(\d+\.\d+)\s+Update Details", title, re.IGNORECASE)
        if not match:
            continue
        version = match.group(1)
        start = parse_date(str(item.get("start_time", "")))
        end = parse_date(str(item.get("end_time", "")))
        if start and end:
            patches[version] = {"start_date": start, "end_date": end}

    candidates: List[Dict[str, Any]] = []
    for item in announcements:
        title = item.get("title", "") or ""
        if "Event Wish" not in title:
            continue
        if "Epitome Invocation" in title:
            continue
        content = strip_html(item.get("content", "") or "")
        version_match = VERSION_RE.search(content) or VERSION_RE.search(title)
        if not version_match:
            continue
        version = version_match.group(1)
        patch = patches.get(version)
        if not patch:
            continue
        start_date, end_date = parse_genshin_dates(content, patch["start_date"])
        if not start_date or not end_date:
            continue
        names = GS_CHAR_RE.findall(content)
        if not names:
            continue
        five_names = [names[0][1]]
        four_names = []
        for entry in names[1:]:
            name = entry[1]
            if name not in five_names and name not in four_names:
                four_names.append(name)
        candidates.append({
            "version": version,
            "start_date": start_date,
            "end_date": end_date,
            "five_names": five_names,
            "four_names": four_names,
            "source_id": str(item.get("ann_id", "")),
        })

    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for candidate in candidates:
        key = (candidate["version"], candidate["start_date"])
        target = grouped.setdefault(key, {
            "version": candidate["version"],
            "start_date": candidate["start_date"],
            "end_date": candidate["end_date"],
            "five_names": [],
            "four_names": [],
            "source_ids": [],
        })
        for name in candidate["five_names"]:
            if name not in target["five_names"]:
                target["five_names"].append(name)
        for name in candidate["four_names"]:
            if name not in target["four_names"]:
                target["four_names"].append(name)
        target["source_ids"].append(candidate["source_id"])

    starts_by_version: Dict[str, List[str]] = {}
    for version, start_date in grouped:
        starts_by_version.setdefault(version, []).append(start_date)
    for version in starts_by_version:
        starts_by_version[version] = sorted(set(starts_by_version[version]))

    banners: List[Dict[str, Any]] = []
    for (version, start_date), data in grouped.items():
        phase = starts_by_version[version].index(start_date) + 1
        source_ids = data["source_ids"]
        source_url = GENSHIN_DETAIL.format(id=source_ids[0]) if source_ids else GENSHIN_SITE
        banner = make_banner(
            0, version, phase, start_date, data["end_date"],
            data["five_names"], data["four_names"],
            source_url, ",".join(source_ids), catalog_lookup,
        )
        if banner:
            banners.append(banner)

    return banners, patches


def fetch_content_list(app: str, channel: str, lang: str) -> List[Dict[str, Any]]:
    url = CONTENT_API.format(app=app)
    query = urllib.parse.urlencode({
        "iPage": 1,
        "iPageSize": 50,
        "sLangKey": lang,
        "isPreview": 0,
        "iChanId": channel,
    })
    payload = fetch_json(f"{url}?{query}")
    return payload.get("data", {}).get("list", [])


def fetch_content_detail(app: str, content_id: str, lang: str) -> Dict[str, Any]:
    url = CONTENT_DETAIL_API.format(app=app)
    query = urllib.parse.urlencode({
        "iPage": 1,
        "iPageSize": 10,
        "sLangKey": lang,
        "isPreview": 0,
        "iInfoId": content_id,
    })
    payload = fetch_json(f"{url}?{query}")
    return payload.get("data", {}) or {}


def parse_zzz_data(catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    items = fetch_content_list(ZZZ_APP, ZZZ_CHANNEL, "en-us")
    patch_starts: Dict[str, str] = {}
    for item in items:
        title = item.get("sTitle", "") or ""
        match = re.search(r"Version\s+(\d+\.\d+).*Update Announcement", title, re.IGNORECASE)
        if match:
            start = parse_date(str(item.get("dtStartTime", "")))
            if start:
                patch_starts[match.group(1)] = start

    banners: List[Dict[str, Any]] = []
    patches: Dict[str, Dict[str, str]] = {}
    for item in items:
        title = item.get("sTitle", "") or ""
        match = re.search(r"V(\d+\.\d+) Limited-Time Channels \(Phase (I|II)\)", title, re.IGNORECASE)
        if not match:
            continue
        version = match.group(1)
        phase = 1 if match.group(2).upper() == "I" else 2
        content_id = str(item.get("iInfoId", ""))
        detail = fetch_content_detail(ZZZ_APP, content_id, "en-us")
        content = strip_html(detail.get("sContent", "") or "")
        if not content:
            continue

        after_update = re.search(
            r"After the Version\s+\d+\.\d+\s+Update\s*[–-]\s*"
            r"(\d{4}/\d{1,2}/\d{1,2})\s+\d{1,2}:\d{2}",
            content,
        )
        if after_update:
            start_date = patch_starts.get(version)
            end_date = parse_date(after_update.group(1))
        else:
            period = re.search(
                r"(\d{4}/\d{1,2}/\d{1,2})\s+\d{1,2}:\d{2}.*?[–-]\s*"
                r"(\d{4}/\d{1,2}/\d{1,2})\s+\d{1,2}:\d{2}",
                content,
            )
            start_date = parse_date(period.group(1)) if period else None
            end_date = parse_date(period.group(2)) if period else None
        if not start_date or not end_date:
            continue

        agents = []
        for name in ZZZ_AGENT_RE.findall(content):
            if name not in agents:
                agents.append(name)
        if not agents:
            continue

        banner = make_banner(
            2, version, phase, start_date, end_date,
            agents, [],
            ZZZ_SITE.format(id=content_id), content_id, catalog_lookup,
        )
        if banner:
            banners.append(banner)
            existing_patch = patches.get(version)
            if not existing_patch:
                patches[version] = {"start_date": start_date, "end_date": end_date}
            else:
                existing_patch["start_date"] = min(existing_patch["start_date"], start_date)
                existing_patch["end_date"] = max(existing_patch["end_date"], end_date)

    return banners, patches


def parse_hi3_data(catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    items = fetch_content_list(HI3_APP, HI3_CHANNEL, "en-us")
    banners: List[Dict[str, Any]] = []
    patches: Dict[str, Dict[str, str]] = {}

    for item in items:
        title = item.get("sTitle", "") or ""
        match = re.search(r"v(\d+\.\d+)\s+.*Update Announcement", title, re.IGNORECASE)
        if not match:
            continue
        version = match.group(1)
        content_id = str(item.get("iInfoId", ""))
        detail = fetch_content_detail(HI3_APP, content_id, "en-us")
        raw_content = detail.get("sContent", "") or ""
        content = strip_html(raw_content)
        if not content:
            continue

        year = datetime.now(timezone.utc).year
        start_time = str(detail.get("dtStartTime", "") or item.get("dtStartTime", ""))
        start_year = parse_date(start_time)
        if start_year:
            year = int(start_year[:4])

        period = re.search(r"\(([A-Z]{3})\s+(\d{1,2})\s*~\s*([A-Z]{3})\s+(\d{1,2})\)", content)
        start_date = parse_month_day(period.group(1), period.group(2), year) if period else None
        end_date = parse_month_day(period.group(3), period.group(4), year) if period else None
        if not start_date or not end_date:
            continue

        suits = []
        for name in re.findall(
            r"New (?:IMG-type )?S-rank Battlesuit\s+([^<]+)",
            raw_content,
            re.IGNORECASE,
        ):
            clean_name = strip_html(name).strip()
            if clean_name and clean_name not in suits:
                suits.append(clean_name)
        if not suits:
            for name in HI3_SUIT_RE.findall(content):
                words = name.split()
                half = len(words) // 2
                if half and words[:half] == words[half:]:
                    name = " ".join(words[:half])
                if name not in suits:
                    suits.append(name)
        if not suits:
            continue

        banner = make_banner(
            3, version, 1, start_date, end_date,
            suits, [],
            HI3_SITE.format(id=content_id), content_id, catalog_lookup,
        )
        if banner:
            banners.append(banner)
            patches[version] = {"start_date": start_date, "end_date": end_date}
            break

    return banners, patches


def extract_hsr_date_ranges(content: str) -> List[Tuple[str, str]]:
    ranges: List[Tuple[str, str]] = []
    for raw_start, raw_end in HSR_DATE_RANGE_RE.findall(content or ""):
        start_date = parse_date(raw_start)
        end_date = parse_date(raw_end)
        if start_date and end_date:
            ranges.append((start_date, end_date))
    for raw_start, raw_end in HSR_RU_DATE_RANGE_RE.findall(content or ""):
        start_date = parse_ru_date(raw_start)
        end_date = parse_ru_date(raw_end)
        if start_date and end_date:
            ranges.append((start_date, end_date))
    return ranges


def select_hsr_phase_dates(ranges: List[Tuple[str, str]], phase: int) -> Tuple[Optional[str], Optional[str]]:
    if not ranges:
        return None, None
    if len(ranges) == 1:
        return ranges[0]
    if phase == 2:
        latest_start = max(r[0] for r in ranges)
        return min((r for r in ranges if r[0] == latest_start), key=lambda r: r[1])
    earliest_start = min(r[0] for r in ranges)
    return min((r for r in ranges if r[0] == earliest_start), key=lambda r: r[1])


def _clean_hsr_name(name: str) -> str:
    return re.sub(r"^(?:and|и)\s+", "", (name or "").strip(), flags=re.IGNORECASE).strip()


def parse_hsr_banner_content(
    content: str,
    phase: int,
) -> Tuple[Optional[str], Optional[str], List[str], List[str]]:
    ranges = extract_hsr_date_ranges(content)
    start_date, end_date = select_hsr_phase_dates(ranges, phase)
    if not start_date or not end_date:
        return None, None, [], []

    five_names: List[str] = []
    four_names: List[str] = []

    for match in HSR_FIVE_EN_WARP_RE.findall(content):
        clean_name = _clean_hsr_name(match)
        if clean_name and clean_name not in five_names:
            five_names.append(clean_name)

    if not five_names:
        for block in HSR_FIVE_EN_LIST_RE.findall(content):
            for match in HSR_NAME_EN_RE.findall(block):
                clean_name = _clean_hsr_name(match)
                if clean_name and clean_name not in five_names:
                    five_names.append(clean_name)

    for block in HSR_FOUR_EN_BLOCK_RE.findall(content):
        for match in HSR_NAME_EN_RE.findall(block):
            clean_name = _clean_hsr_name(match)
            if clean_name and clean_name not in five_names and clean_name not in four_names:
                four_names.append(clean_name)
        if four_names:
            break

    if not five_names:
        for match in HSR_FIVE_RU_RE.findall(content):
            clean_name = _clean_hsr_name(match)
            if clean_name and clean_name not in five_names:
                five_names.append(clean_name)
        for block in HSR_FIVE_RU_LIST_RE.findall(content):
            for match in HSR_NAME_RU_RE.findall(block):
                clean_name = _clean_hsr_name(match)
                if clean_name and clean_name not in five_names:
                    five_names.append(clean_name)

    if not four_names:
        block = HSR_FOUR_RU_BLOCK_RE.search(content)
        if block:
            for match in HSR_NAME_RU_RE.findall(block.group(1)):
                clean_name = _clean_hsr_name(match)
                if clean_name and clean_name not in five_names and clean_name not in four_names:
                    four_names.append(clean_name)

    return start_date, end_date, five_names, four_names


def _fetch_hsr_hoyolab_posts(lang: str) -> List[Dict[str, Any]]:
    news = fetch_json(HSR_HOYOLAB_LIST, lang=lang)
    return news.get("data", {}).get("list", [])


def parse_hsr_data(catalog_lookup: Dict[int, Dict[str, Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    banners: List[Dict[str, Any]] = []
    patches: Dict[str, Dict[str, str]] = {}

    items = fetch_content_list(HSR_APP, HSR_CHANNEL, "en-us")
    for item in items:
        title = item.get("sTitle", "") or ""
        match = re.search(r"Version\s+(\d+\.\d+).*Update Details", title, re.IGNORECASE)
        if not match:
            continue
        version = match.group(1)
        content_id = str(item.get("iInfoId", ""))
        detail = fetch_content_detail(HSR_APP, content_id, "en-us")
        content = strip_html(detail.get("sContent", "") or "")
        if not content:
            continue
        start_date = parse_date(str(detail.get("dtStartTime", "") or item.get("dtStartTime", "")))
        end_match = re.search(
            r"Version\s+\d+\.\d+\s+will run from after the Version\s+\d+\.\d+\s+update until\s+"
            r"(\d{4}/\d{1,2}/\d{1,2})",
            content,
        )
        end_date = parse_date(end_match.group(1)) if end_match else None
        if start_date and end_date:
            patches[version] = {"start_date": start_date, "end_date": end_date}
            break

    posts_by_id: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for lang in ("en-us", "ru-ru"):
        try:
            for entry in _fetch_hsr_hoyolab_posts(lang):
                post = entry.get("post", {}) or {}
                post_id = str(post.get("post_id", ""))
                if post_id and post_id not in posts_by_id:
                    posts_by_id[post_id] = (lang, post)
        except Exception as error:
            print(f"[OfficialParser] HSR HoYoLAB list ({lang}) failed: {error}")

    if not posts_by_id:
        return banners, patches

    today = datetime.now(timezone.utc).date()
    for post_id, (lang, post) in posts_by_id.items():
        subject = post.get("subject", "") or ""
        match = re.search(
            r"(?:Version\s+(\d+\.\d+)\s+Event Warp:\s+Phase\s+(II|I)\b|"
            r"Прыжок события версии\s+(\d+\.\d+):\s*(первая|вторая)\s+фаза)",
            subject,
            re.IGNORECASE,
        )
        if not match:
            continue
        version = match.group(1) or match.group(3)
        phase_text = match.group(2) or match.group(4) or "I"
        phase = 2 if phase_text.upper() in ("II", "ВТОРАЯ") else 1

        banner = None
        for attempt_lang in (lang, "ru-ru" if lang == "en-us" else "en-us"):
            try:
                detail = fetch_json(
                    f"{HSR_HOYOLAB_POST}?{urllib.parse.urlencode({'post_id': post_id})}",
                    lang=attempt_lang,
                )
                post_obj = detail.get("data", {}).get("post", {}).get("post", {}) or {}
                content = extract_hoyolab_text(post_obj)
            except Exception as error:
                print(f"[OfficialParser] HSR post {post_id} ({attempt_lang}) failed: {error}")
                continue
            if not content:
                continue

            start_date, end_date, five_names, four_names = parse_hsr_banner_content(content, phase)
            if not start_date or not end_date:
                continue
            if datetime.strptime(end_date, "%Y-%m-%d").date() < today - timedelta(days=45):
                break

            banner = make_banner(
                1, version, phase, start_date, end_date,
                five_names, four_names,
                HSR_ARTICLE.format(id=post_id), post_id, catalog_lookup,
            )
            if banner:
                break

        if banner:
            banners.append(banner)

    return banners, patches


def parse_all_official_data(catalog_path: str) -> Dict[str, Any]:
    catalog_lookup = load_catalog_lookup(catalog_path)
    banners: List[Dict[str, Any]] = []
    patches: Dict[int, Dict[str, Dict[str, str]]] = {0: {}, 1: {}, 2: {}, 3: {}}
    errors: Dict[int, str] = {}

    parsers = [(0, parse_genshin_data), (2, parse_zzz_data), (3, parse_hi3_data), (1, parse_hsr_data)]
    for game_type, parser in parsers:
        try:
            game_banners, game_patches = parser(catalog_lookup)
            banners.extend(game_banners)
            patches[game_type].update(game_patches)
        except Exception as error:
            errors[game_type] = str(error)
            print(f"[OfficialParser] {GAME_NAMES[game_type]} failed: {error}")

    return {"banners": banners, "patches": patches, "errors": errors}


def parse_all_official_banners(catalog_path: str) -> List[Dict[str, Any]]:
    return parse_all_official_data(catalog_path)["banners"]


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    catalog_file = os.path.join(base_dir, "game_catalog.json")
    result = parse_all_official_data(catalog_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
