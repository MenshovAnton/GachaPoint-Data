#!/usr/bin/env python3
"""
Official promo-code verifier for HoYoverse games.

The verifier searches official HoYoverse announcement/news text for candidate
codes. A code is published automatically only when the exact code is found in
an official source and reward quantities can be extracted from the surrounding
text. Everything ambiguous is returned as a review candidate for Telegram
moderation instead of being published.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from scripts.parsers.fandom_parser import parse_rewards_from_text
from scripts.parsers.official_banners_parser import (
    GENSHIN_ANN_URL,
    GENSHIN_DETAIL,
    GENSHIN_SITE,
    HI3_APP,
    HI3_CHANNEL,
    HI3_SITE,
    HSR_APP,
    HSR_CHANNEL,
    HSR_HOYOLAB_POST,
    HSR_SITE,
    ZZZ_APP,
    ZZZ_CHANNEL,
    ZZZ_SITE,
    extract_hoyolab_text,
    fetch_content_detail,
    fetch_content_list,
    fetch_json,
    strip_html,
)

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")
HOYOLAB_NEWS_URL = "https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList"
HOYOLAB_ARTICLE_URL = "https://www.hoyolab.com/article/{id}"
HOYOLAB_GIDS = {0: 2, 1: 6, 2: 8, 3: 1}
GENSHIN_CONTENT_APP = "a1b1f9d3315447cc"
GENSHIN_CONTENT_CHANNEL = "395"
HSR_ANN_CONTENT_URL = (
    "https://sg-hkrpg-api.hoyoverse.com/common/hkrpg_global/announcement/api/getAnnContent"
    "?game=hkrpg&game_biz=hkrpg_global&lang=en&bundle_id=hkrpg_global"
    "&platform=pc&region=prod_official_usa&level=60&uid=100000000"
)
CONTENT_APP_MAP = {
    0: GENSHIN_CONTENT_APP,
    1: HSR_APP,
    2: ZZZ_APP,
    3: HI3_APP,
}
DETAIL_ID_RE = re.compile(r"/detail/(\d+)")
HOYOLAB_ID_RE = re.compile(r"/article/(\d+)")

CODE_URL_RE = re.compile(
    r"(?:gift|redemption|index\.html)\?(?:[^\s\"'<>]*&)?(?:code|cdkey)=([A-Za-z0-9_-]{4,30})",
    re.IGNORECASE,
)
CODE_CONTEXT_RE = re.compile(
    r"(?:promo\s*codes?|redemption\s*codes?|gift\s*codes?|special\s*codes?|codes?|промокод(?:ы|а)?|код(?:ы)?)"
    r"\s*[:：\-–—]?\s*([A-Za-z0-9_-]{6,20}(?:\s*[,/]\s*[A-Za-z0-9_-]{6,20})*)",
    re.IGNORECASE,
)
EXPIRY_HINT_RE = re.compile(
    r"(?:valid\s+(?:until|through|till)|expires?|ends?|until|до)\D{0,32}"
    r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    re.IGNORECASE,
)

DISALLOWED_TOKENS = {
    "CODE", "CODES", "PROMOCODE", "PROMO", "REWARD", "REWARDS", "GIFT",
    "UPDATE", "VERSION", "SEASON", "PHASE", "EVENT", "PROGRAM", "STREAM",
    "SERVER", "SERVERS", "REGION", "BANNER", "NOTICE", "DETAIL", "DETAILS", "STATUS",
    "PLAYER", "PLAYERS", "TRAVELER", "TRAVELERS", "TRAILBLAZER", "TRAILBLAZERS",
    "PROXY", "PROXIES", "CAPTAIN", "CAPTAINS", "PLEASE", "GLOBAL", "SPECIAL",
    "PREVIEW", "RELEASE", "VACATION", "REDEEM", "REDEMPTION", "OFFICIAL",
    "ACCOUNT", "LIMITED", "ANDROID", "IPHONE", "WINDOWS", "DESKTOP",
    "HOYOVERSE", "HOYOLAB", "GENSHIN", "STARRAIL", "ZENLESS", "HONKAI",
    "CHARACTER", "CHARACTERS", "WEAPON", "WEAPONS", "TWITTER", "YOUTUBE",
    "DISCORD", "TWITCH", "FACEBOOK", "TELEGRAM", "INSTAGRAM", "TIKTOK",
    "ENGLISH", "RUSSIAN", "CHINESE", "JAPANESE", "KOREAN", "DOWNLOAD",
    "INSTALL", "DUALSHOCK", "PLAYSTATION", "CONTROLLER",
}

GAME_NAMES = {
    0: "Genshin Impact",
    1: "Honkai: Star Rail",
    2: "Zenless Zone Zero",
    3: "Honkai Impact 3rd",
}

REDEEM_URLS = {
    0: "https://genshin.hoyoverse.com/ru/gift?code={code}",
    1: "https://hsr.hoyoverse.com/gift?code={code}",
    2: "https://zenless.hoyoverse.com/redemption?code={code}",
    3: "https://act.hoyoverse.com/puzzle/bh3/pz_u6h7mQo34g/index.html?cdkey={code}",
}


def game_name(game_type: int) -> str:
    return GAME_NAMES.get(game_type, f"Game {game_type}")


def redeem_url(game_type: int, code: str) -> str:
    template = REDEEM_URLS.get(game_type)
    return template.format(code=code) if template else ""


def _fetch_json_cached(url: str, lang: Optional[str] = None) -> Any:
    if not hasattr(_fetch_json_cached, "cache"):
        _fetch_json_cached.cache = {}
    key = (url, lang or "")
    if key not in _fetch_json_cached.cache:
        _fetch_json_cached.cache[key] = fetch_json(url, lang=lang)
    return _fetch_json_cached.cache[key]


def _official_text(
    game_type: int,
    title: str,
    url: str,
    source_id: str,
    text: str,
) -> Optional[Dict[str, Any]]:
    clean = strip_html(text or "")
    if not clean:
        return None
    return {
        "game_type": game_type,
        "title": title or "",
        "url": url or "",
        "source_id": str(source_id or ""),
        "text": clean,
    }


def _recent(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return items[:limit]


def collect_official_sources(recent_limit: int = 10) -> List[Dict[str, Any]]:
    """Collects recent official texts that may contain promo codes."""
    sources: List[Dict[str, Any]] = []

    for lang in ("en-us", "ru-ru"):
        try:
            payload = _fetch_json_cached(GENSHIN_ANN_URL, lang=lang)
            for item in payload.get("data", {}).get("list", []):
                entry = _official_text(
                    0,
                    item.get("title", ""),
                    GENSHIN_SITE,
                    item.get("ann_id", ""),
                    item.get("content", ""),
                )
                if entry:
                    sources.append(entry)
        except Exception as error:
            print(f"[OfficialCodes] Genshin announcements ({lang}) failed: {error}")

    for lang in ("en-us", "ru-ru"):
        try:
            payload = _fetch_json_cached(HSR_ANN_CONTENT_URL, lang=lang)
            for item in payload.get("data", {}).get("list", []):
                entry = _official_text(
                    1,
                    item.get("title", ""),
                    HSR_SITE.format(id=item.get("ann_id", "")),
                    item.get("ann_id", ""),
                    item.get("content", ""),
                )
                if entry:
                    sources.append(entry)
        except Exception as error:
            print(f"[OfficialCodes] HSR announcements ({lang}) failed: {error}")

    content_sources = (
        (0, GENSHIN_CONTENT_APP, GENSHIN_CONTENT_CHANNEL, GENSHIN_DETAIL, ("en-us", "ru-ru")),
        (1, HSR_APP, HSR_CHANNEL, HSR_SITE, ("en-us",)),
        (1, HSR_APP, "248", HSR_SITE, ("en-us",)),
        (1, HSR_APP, "249", HSR_SITE, ("en-us",)),
        (2, ZZZ_APP, ZZZ_CHANNEL, ZZZ_SITE, ("en-us",)),
        (3, HI3_APP, HI3_CHANNEL, HI3_SITE, ("en-us",)),
    )
    seen_content = set()
    for game_type, app, channel, site, langs in content_sources:
        for lang in langs:
            try:
                items = fetch_content_list(app, channel, lang)
                for item in _recent(items, recent_limit):
                    content_id = str(item.get("iInfoId", ""))
                    if not content_id or (game_type, content_id, lang) in seen_content:
                        continue
                    seen_content.add((game_type, content_id, lang))
                    detail = fetch_content_detail(app, content_id, lang)
                    entry = _official_text(
                        game_type,
                        item.get("sTitle", ""),
                        site.format(id=content_id),
                        content_id,
                        detail.get("sContent", "") or item.get("sContent", ""),
                    )
                    if entry:
                        sources.append(entry)
            except Exception as error:
                print(f"[OfficialCodes] {game_name(game_type)} content ({channel}/{lang}) failed: {error}")

    hoyolab_keywords = (
        "code", "redeem", "livestream", "special program", "gift", "reward",
        "промокод", "код", "стрим", "спецпрограмм", "наград", "подар",
    )
    for game_type, gid in HOYOLAB_GIDS.items():
        for lang in ("en-us", "ru-ru"):
            try:
                payload = _fetch_json_cached(
                    f"{HOYOLAB_NEWS_URL}?gids={gid}&type=1&page_size=30&client_type=4",
                    lang=lang,
                )
                for idx, wrapper in enumerate(payload.get("data", {}).get("list", [])):
                    post = wrapper.get("post", {}) or {}
                    post_id = str(post.get("post_id", ""))
                    if not post_id:
                        continue
                    subject = post.get("subject", "") or ""
                    text = extract_hoyolab_text(post)
                    needs_full = idx < 5 or any(kw in subject.lower() or kw in text.lower() for kw in hoyolab_keywords)
                    if needs_full:
                        try:
                            full_payload = _fetch_json_cached(
                                f"{HSR_HOYOLAB_POST}?post_id={post_id}",
                                lang=lang,
                            )
                            full_post = full_payload.get("data", {}).get("post", {}).get("post", {}) or {}
                            full_text = extract_hoyolab_text(full_post)
                            if full_text:
                                text = full_text
                        except Exception:
                            pass
                    entry = _official_text(
                        game_type,
                        subject,
                        HOYOLAB_ARTICLE_URL.format(id=post_id),
                        post_id,
                        text,
                    )
                    if entry:
                        sources.append(entry)
            except Exception as error:
                print(f"[OfficialCodes] HoYoLAB gid {gid} ({lang}) failed: {error}")

    print(f"[OfficialCodes] Collected {len(sources)} official text sources.")
    return sources


def sources_from_candidate_urls(
    candidates: List[Dict[str, Any]],
    official_hoyolab_ids: Optional[set] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Fetches official pages referenced by candidate records."""
    sources: List[Dict[str, Any]] = []
    seen_urls = set()

    for candidate in candidates:
        url = candidate.get("source_url")
        if not url or url in seen_urls:
            continue
        if len(sources) >= limit:
            break
        seen_urls.add(url)
        game_type = int(candidate.get("game_type", 0))
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""

        if host.endswith("hoyolab.com"):
            match = HOYOLAB_ID_RE.search(parsed.path)
            if not match:
                continue
            post_id = match.group(1)
            if official_hoyolab_ids is not None and post_id not in official_hoyolab_ids:
                continue
            try:
                payload = _fetch_json_cached(
                    f"{HSR_HOYOLAB_POST}?post_id={post_id}",
                    lang="en-us",
                )
                full_post = (
                    payload.get("data", {})
                    .get("post", {})
                    .get("post", {})
                    or {}
                )
                content = extract_hoyolab_text(full_post)
                entry = _official_text(game_type, url, url, post_id, content)
                if entry:
                    sources.append(entry)
            except Exception as error:
                print(f"[OfficialCodes] HoYoLAB article {post_id} failed: {error}")
            continue

        if host.endswith("hoyoverse.com"):
            match = DETAIL_ID_RE.search(parsed.path)
            if not match:
                continue
            content_id = match.group(1)
            app = CONTENT_APP_MAP.get(game_type)
            if not app:
                continue
            try:
                detail = fetch_content_detail(app, content_id, "en-us")
                entry = _official_text(
                    game_type,
                    url,
                    url,
                    content_id,
                    detail.get("sContent", ""),
                )
                if entry:
                    sources.append(entry)
            except Exception as error:
                print(f"[OfficialCodes] Official detail {content_id} failed: {error}")

    if sources:
        print(f"[OfficialCodes] Fetched {len(sources)} candidate source pages.")
    return sources


def _code_pattern(code: str) -> re.Pattern:
    return re.compile(
        r"(?<![A-Za-z0-9_-])" + re.escape(code) + r"(?![A-Za-z0-9_-])",
        re.IGNORECASE,
    )


def _context(text: str, code: str, radius: int = 350) -> str:
    match = _code_pattern(code).search(text)
    if not match:
        return text[: radius * 2]
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end]


def extract_expiry(context: str) -> Tuple[Optional[str], str]:
    matches = EXPIRY_HINT_RE.findall(context or "")
    if not matches:
        return None, "unknown"
    raw = matches[-1]
    parts = re.split(r"[/-]", raw)
    if len(parts) != 3:
        return None, "unknown"
    try:
        year, month, day = (int(part) for part in parts)
    except ValueError:
        return None, "unknown"
    return f"{year:04d}-{month:02d}-{day:02d}T23:59:59Z", "official"


def _rewards(context: str, game_type: int) -> Tuple[Optional[str], Optional[str], List[str]]:
    desc_ru, desc_en, reward_types = parse_rewards_from_text(context, game_type)
    if not desc_ru or not desc_en:
        return None, None, []
    if not any(ch.isdigit() for ch in desc_ru) and not any(ch.isdigit() for ch in desc_en):
        return None, None, []
    return desc_ru, desc_en, reward_types


def verify_code(
    game_type: int,
    code: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verifies one code against collected official texts."""
    clean_code = (code or "").strip().upper()
    result: Dict[str, Any] = {
        "game_type": game_type,
        "code": clean_code,
        "status": "not_found",
        "source_url": None,
        "source_id": None,
        "source_title": None,
        "rewards_description_ru": None,
        "rewards_description_en": None,
        "reward_types": [],
        "expires_at": None,
        "expiry_confidence": "unknown",
        "reason": "official_source_not_found",
    }
    if not clean_code or not CODE_RE.match(clean_code):
        return result

    pattern = _code_pattern(clean_code)
    best = None
    ambiguous = None
    for source in sources:
        if source.get("game_type") != game_type:
            continue
        text = source.get("text", "")
        if not pattern.search(text):
            continue
        context = _context(text, clean_code)
        desc_ru, desc_en, reward_types = _rewards(context, game_type)
        if desc_ru and desc_en:
            best = {
                "source": source,
                "desc_ru": desc_ru,
                "desc_en": desc_en,
                "reward_types": reward_types,
                "context": context,
            }
            break
        if ambiguous is None:
            ambiguous = {"source": source, "context": context}

    if best:
        expires_at, confidence = extract_expiry(best["context"])
        result.update({
            "status": "verified",
            "source_url": best["source"]["url"],
            "source_id": best["source"]["source_id"],
            "source_title": best["source"]["title"],
            "rewards_description_ru": best["desc_ru"],
            "rewards_description_en": best["desc_en"],
            "reward_types": best["reward_types"],
            "expires_at": expires_at,
            "expiry_confidence": confidence,
            "reason": "official_source_confirmed",
        })
        return result

    if ambiguous:
        result.update({
            "status": "ambiguous",
            "source_url": ambiguous["source"]["url"],
            "source_id": ambiguous["source"]["source_id"],
            "source_title": ambiguous["source"]["title"],
            "reason": "official_source_without_rewards",
        })
    return result


def _is_valid_discovered_token(raw_token: str, from_url: bool) -> bool:
    token = (raw_token or "").strip().upper()
    if not CODE_RE.match(token):
        return False
    if token in DISALLOWED_TOKENS or token.isdigit():
        return False
    if re.fullmatch(r"(?:19|20)\d{2}", token):
        return False
    if from_url:
        return len(token) >= 4
    if any(ch.isdigit() for ch in token):
        return len(token) >= 6
    return raw_token.strip().isupper() and len(token) >= 8


def discover_official_codes(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Finds conservative code-like tokens in official texts."""
    discovered: List[Dict[str, Any]] = []
    seen = set()
    for source in sources:
        game_type = source.get("game_type", 0)
        text = source.get("text", "") or ""
        candidates: List[Tuple[str, bool]] = []
        for match in CODE_URL_RE.finditer(text):
            candidates.append((match.group(1), True))
        for match in CODE_CONTEXT_RE.finditer(text):
            for part in re.split(r"[,/]", match.group(1)):
                candidates.append((part.strip(), False))

        for raw_token, from_url in candidates:
            if not _is_valid_discovered_token(raw_token, from_url=from_url):
                continue
            token = raw_token.strip().upper()
            key = (game_type, token)
            if key in seen:
                continue
            seen.add(key)
            discovered.append({
                "game_type": game_type,
                "code": token,
                "source_url": source.get("url"),
                "source_id": source.get("source_id"),
            })
    return discovered


def verify_candidates(
    candidates: List[Dict[str, Any]],
    sources: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Verifies candidates and returns one result per (game_type, code)."""
    if sources is None:
        texts = collect_official_sources()
        official_hoyolab_ids = {
            source.get("source_id")
            for source in texts
            if "hoyolab.com" in (source.get("url") or "")
        }
        texts = texts + sources_from_candidate_urls(
            candidates,
            official_hoyolab_ids=official_hoyolab_ids,
        )
    else:
        texts = sources
    results: List[Dict[str, Any]] = []
    seen = set()

    for candidate in candidates:
        game_type = int(candidate.get("game_type", 0))
        code = (candidate.get("code") or "").strip().upper()
        key = (game_type, code)
        if key in seen:
            continue
        seen.add(key)
        results.append(verify_code(game_type, code, texts))

    for candidate in discover_official_codes(texts):
        game_type = int(candidate.get("game_type", 0))
        code = candidate.get("code", "")
        key = (game_type, code)
        if key in seen:
            continue
        seen.add(key)
        verified = verify_code(game_type, code, texts)
        if verified.get("status") == "verified":
            results.append(verified)

    return results
