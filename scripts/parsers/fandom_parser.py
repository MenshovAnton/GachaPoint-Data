#!/usr/bin/env python3
"""
Fandom MediaWiki API Parser for HoYoverse Games (Genshin, HSR, ZZZ, HI3)
Extracts active, stream, and expired promo codes with resilient parsing
and anchor-based expiration dates (preventing the sliding window bug).
"""

import re
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

GAMES_CONFIG = {
    0: {
        "name": "Genshin Impact",
        "wiki": "genshin-impact",
        "page": "Promotional_Code",
        "primary_reward": "PRIMOGEM",
        "primary_name_ru": "Камней Истока",
        "primary_name_en": "Primogems"
    },
    1: {
        "name": "Honkai: Star Rail",
        "wiki": "honkai-star-rail",
        "page": "Redemption_Code",
        "primary_reward": "JADE",
        "primary_name_ru": "Звёздного нефрита",
        "primary_name_en": "Stellar Jade"
    },
    2: {
        "name": "Zenless Zone Zero",
        "wiki": "zenless-zone-zero",
        "page": "Redemption_Code",
        "primary_reward": "POLYCHROME",
        "primary_name_ru": "Полихромов",
        "primary_name_en": "Polychromes"
    },
    3: {
        "name": "Honkai Impact 3rd",
        "wiki": "honkaiimpact3",
        "page": "Exchange_Rewards",
        "primary_reward": "CRYSTAL",
        "primary_name_ru": "Кристаллов",
        "primary_name_en": "Crystals"
    }
}

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_URL_RE = re.compile(r"https?://[^\s\]<>|\"']+")
OFFICIAL_SOURCE_HOSTS = ("hoyoverse.com", "hoyolab.com", "x.com", "twitter.com")
DISALLOWED_CODES = {
    "CODE", "PROMOCODE", "ITEM", "YES", "NO", "REWARDS", "GLOBAL",
    "ONLINE", "WEBSITE", "SERVER", "NOTES", "DURATION", "EXCHANGE",
    "REDEMPTION", "DATE", "EXPIRY", "DISCOVERY", "UNKNOWN", "VERSION",
    "DETAILS", "REWARD", "STATUS", "STREAM", "ACTIVE", "EXPIRED",
    "SPECIAL", "PROGRAM", "UPDATE", "COLLAB", "TWITTER", "DISCORD",
    "YOUTUBE", "TWITCH", "TIKTOK", "REDDIT", "HOYOLAB", "OFFICIAL"
}


def fetch_page_wikitext(wiki_name: str, page_title: str) -> Optional[str]:
    """Fetches wikitext from MediaWiki API with timeout and robust headers."""
    api_url = f"https://{wiki_name}.fandom.com/api.php"
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "wikitext",
        "format": "json"
    }
    url = f"{api_url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointDataHub/2.0"}
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                if "parse" in data and "wikitext" in data["parse"]:
                    return data["parse"]["wikitext"].get("*", "")
    except Exception as e:
        print(f"[Parser] Failed to fetch {wiki_name}/{page_title}: {e}")
    return None


def split_active_and_expired(full_text: str, game_type: int) -> Tuple[str, str]:
    """Splits full wikitext into active and expired sections cleanly."""
    active_text = full_text
    expired_text = ""

    split_patterns = [
        r'==+\s*(?:Expired|Past|Inactive|History|Previous|Legacy|Old)',
        r'<!--\s*expired\s*-->'
    ]

    best_idx = -1
    for pat in split_patterns:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m and (best_idx == -1 or m.start() < best_idx):
            best_idx = m.start()

    if best_idx != -1:
        active_text = full_text[:best_idx]
        expired_text = full_text[best_idx:]

    # Clean out comments and editorial instructions
    active_text = re.sub(r'<!--\s*To add to this list[\s\S]*?-->', '', active_text, flags=re.IGNORECASE)
    return active_text, expired_text


GENERIC_ITEM_ALIASES = {
    "guide to charity": ("Указания о «Милосердии»", "Guide to Charity", "TALENT_BOOK"),
    "kristallfold": ("Кристаллический гриб-зонтик", "Kristallfold", "MATERIAL"),
    "energy-replenishing meal": ("Энергетический обед", "Energy-Replenishing Meal", "FOOD"),
}

CURRENCY_ITEM_KEYS = {
    "primogem", "primogems", "stellar jade", "polychrome", "polychromes",
    "crystal", "crystals", "mora", "credit", "credits", "denny", "dennies",
    "coin", "coins", "asterite"
}


def normalize_item_key(name: str) -> str:
    return name.strip().strip('"').strip("“”").lower().replace("’", "'")


def parse_generic_items(row_text: str) -> List[Tuple[str, str, str, int]]:
    items = []
    seen = set()

    def add(raw_name: str, raw_quantity: str):
        name = raw_name.strip().strip('"').strip("“”")
        quantity = raw_quantity.replace(",", "").replace(" ", "")
        key = normalize_item_key(name)
        if not name or not quantity.isdigit() or key in seen or key in CURRENCY_ITEM_KEYS:
            return
        seen.add(key)
        ru_name, en_name, reward_type = GENERIC_ITEM_ALIASES.get(key, (name, name, "ITEM"))
        items.append((ru_name, en_name, reward_type, int(quantity)))

    for block in re.findall(r"\{\{Item List\|([^}]+)\}\}", row_text, re.IGNORECASE):
        for part in block.split(";"):
            match = re.match(r'\s*"?([^"*x×]+?)"?\s*[*x×]\s*([\d,]+)', part, re.IGNORECASE)
            if match:
                add(match.group(1), match.group(2))

    for match in re.finditer(r"\{\{Item\|([^|}]+)\|([^}]*)\}\}", row_text, re.IGNORECASE):
        quantity = re.search(r"quantity\s*=\s*([\d,]+)", match.group(2), re.IGNORECASE)
        if quantity:
            add(match.group(1), quantity.group(1))

    for match in re.finditer(r'"([^"]+)"\s*[*x×]\s*([\d,]+)', row_text):
        add(match.group(1), match.group(2))

    for match in re.finditer(r'(?<![\w])([A-Z][A-Za-z\'’\- ]{2,40}?)\s*[*x×]\s*([\d,]+)', row_text):
        add(match.group(1), match.group(2))

    return items


def parse_rewards_from_text(row_text: str, game_type: int) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Analyzes table row text to determine reward types, RU/EN descriptions."""
    config = GAMES_CONFIG[game_type]
    reward_types = []
    ru_parts = []
    en_parts = []

    # 1. Primary currency: Primogems / Stellar Jade / Polychromes / Crystals
    prim_names = r"(?:Primogem|Stellar Jade|Polychrome|Crystal)s?|Камн[а-яё]* Истока|Зв[её]здн[а-яё]* нефрит[а-яё]*|Полихром[а-яё]*|Кристалл[а-яё]*"
    prim_match = re.search(rf'(?:{prim_names})\s*(?:x|\*|×)\s*(\d+)', row_text, re.IGNORECASE)
    if not prim_match:
        prim_match = re.search(rf'(?:x|\*|×)?\s*(\d+)\s*(?:x|\*|×)?\s*(?:\[\[)?(?:{prim_names})', row_text, re.IGNORECASE)
    if not prim_match:
        prim_match = re.search(r'{{(?:Item\|)?(?:Primogem|Stellar Jade|Polychrome|Crystal)[^}]*?(?:quantity|x|count)\s*=\s*(\d+)', row_text, re.IGNORECASE)
    if not prim_match:
        prim_match = re.search(r'{{Item\|(?:Primogem|Stellar Jade|Polychrome|Crystal)\|(\d+)', row_text, re.IGNORECASE)

    if prim_match:
        amount = prim_match.group(1)
        reward_types.append(config["primary_reward"])
        ru_parts.append(f"{amount} {config['primary_name_ru']}")
        en_parts.append(f"{amount} {config['primary_name_en']}")

    # 2. Secondary currency: Mora / Credits / Dennies / Coins
    sec_names = r"(?:Mora|Credit|Dennie|Denny|Coin)s?|Мор[аы]|Кредит[а-яё]*|Денни|Монет[а-яё]*"
    sec_match = re.search(rf'(?:{sec_names})\s*(?:x|\*|×)\s*([\d,]+(?:\s\d{{3}})*)', row_text, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(rf'(?:x|\*|×)?\s*([\d,]+)\s*(?:x|\*|×)?\s*(?:\[\[)?(?:{sec_names})', row_text, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'{{(?:Item\|)?(?:Mora|Credit|Dennie|Denny|Coin)[^}]*?(?:quantity|x|count)\s*=\s*([\d,]+)', row_text, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'{{Item\|(?:Mora|Credit|Dennie|Denny|Coin)\|([\d,]+)', row_text, re.IGNORECASE)

    if sec_match:
        raw_num = sec_match.group(1).replace(" ", "").replace(",", "")
        if raw_num.isdigit():
            fmt_num = f"{int(raw_num):,}".replace(",", " ")
            sec_type = "MORA" if game_type == 0 else "CREDIT" if game_type == 1 else "DENNY" if game_type == 2 else "COIN"
            sec_name_ru = "Моры" if game_type == 0 else "Кредитов" if game_type == 1 else "Денни" if game_type == 2 else "Монет"
            sec_name_en = "Mora" if game_type == 0 else "Credits" if game_type == 1 else "Dennies" if game_type == 2 else "Coins"
            reward_types.append(sec_type)
            ru_parts.append(f"{fmt_num} {sec_name_ru}")
            en_parts.append(f"{fmt_num} {sec_name_en}")

    # 3. EXP
    exp_match = re.search(r'(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)\s*(?:x|\*|×)\s*(\d+)', row_text, re.IGNORECASE)
    if not exp_match:
        exp_match = re.search(r'(\d+)\s*(?:x|\*|×)?\s*(?:\[\[)?(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)', row_text, re.IGNORECASE)
    if not exp_match:
        exp_match = re.search(r'{{(?:Item\|)?(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)[^}]*?(?:quantity|x|count)\s*=\s*(\d+)', row_text, re.IGNORECASE)
    if not exp_match:
        exp_match = re.search(r'{{Item\|(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)\|(\d+)', row_text, re.IGNORECASE)

    if exp_match:
        amount = exp_match.group(1)
        reward_types.append("EXP")
        is_adv = "adventurer" in row_text.lower()
        exp_ru = "Опыта искателя" if is_adv else "Опыта героя" if game_type == 0 else "Путеводителей" if game_type == 1 else "Журналов" if game_type == 2 else "Опыта"
        exp_en = "Adventurer's Exp" if is_adv else "Hero's Wit" if game_type == 0 else "Traveler's Guides" if game_type == 1 else "Investigator Logs" if game_type == 2 else "EXP"
        ru_parts.append(f"{amount} {exp_ru}")
        en_parts.append(f"{amount} {exp_en}")

    # 4. Asterite (HI3)
    ast_match = re.search(r'{{Item\|Asterite[^}]*?quantity\s*=\s*([\d,]+)', row_text, re.IGNORECASE)
    if not ast_match:
        ast_match = re.search(r'(?:Asterite|Астерит)s?\s*(?:x|\*|\:)?\s*([\d,]+)', row_text, re.IGNORECASE)
    if not ast_match:
        ast_match = re.search(r'([\d,]+)\s*(?:Asterite|Астерит)', row_text, re.IGNORECASE)
    if ast_match:
        amount = ast_match.group(1).replace(",", "").replace(" ", "")
        if amount.isdigit():
            reward_types.append("ASTERITE")
            ru_parts.append(f"{amount} Астерита")
            en_parts.append(f"{amount} Asterite")

    # 5. Coins / Gold (HI3)
    coin_match = re.search(r'([\d,]+)\s*(?:Coins?|Монет)', row_text, re.IGNORECASE)
    if coin_match and "COIN" not in reward_types:
        raw_num = coin_match.group(1).replace(",", "").replace(" ", "")
        if raw_num.isdigit():
            fmt_num = f"{int(raw_num):,}".replace(",", " ")
            reward_types.append("COIN")
            ru_parts.append(f"{fmt_num} Монет")
            en_parts.append(f"{fmt_num} Coins")

    if not ru_parts:
        for ru_name, en_name, reward_type, quantity in parse_generic_items(row_text):
            if reward_type not in reward_types:
                reward_types.append(reward_type)
            ru_parts.append(f"{quantity} {ru_name}")
            en_parts.append(f"{quantity} {en_name}")

    if not ru_parts:
        return None, None, []

    desc_ru = ", ".join(ru_parts)
    desc_en = ", ".join(en_parts)
    return desc_ru, desc_en, reward_types


def extract_code_from_row(row: str) -> Optional[str]:
    """Finds promo code candidate from a table row or template."""
    # Pattern 1: Template parameter e.g. |CODE| or | CODE |
    template_match = re.search(r'(?:^\s*(?:<!--.*?-->)?\s*\|\s*|\|(?:\'\'\')?)([A-Za-z0-9_-]{4,30})(?:\'\'\')?\s*\|', row)
    if template_match:
        candidate = template_match.group(1).strip().upper()
        if CODE_RE.match(candidate) and not DATE_PATTERN.match(candidate) and candidate not in DISALLOWED_CODES:
            return candidate

    # Pattern 2: Bold code (e.g. HI3 tables: |'''CODE'''||)
    bold_match = re.search(r"'''([A-Z0-9_-]{4,25})'''", row)
    if bold_match:
        candidate = bold_match.group(1).strip().upper()
        if CODE_RE.match(candidate) and not DATE_PATTERN.match(candidate) and candidate not in DISALLOWED_CODES:
            return candidate

    # Pattern 3: URL code fallback
    url_match = re.search(r'(?:gift|redemption)\?(?:[^\s"\'<>]*&)?code=([A-Za-z0-9_-]{3,30})', row, re.IGNORECASE)
    if url_match:
        candidate = url_match.group(1).strip().upper()
        if CODE_RE.match(candidate) and candidate not in DISALLOWED_CODES:
            return candidate

    return None


def extract_source_url(row: str) -> Optional[str]:
    for url in SOURCE_URL_RE.findall(row):
        host = urllib.parse.urlparse(url).hostname or ""
        if any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_SOURCE_HOSTS):
            return url.rstrip(".,;)")
    return None


MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def extract_row_dates(row: str) -> List[str]:
    dates = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', row)
    if dates:
        return dates
    parsed = []
    for mon, day, year in re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),\s*(\d{2,4})\b', row, re.IGNORECASE):
        month = MONTH_ABBR.get(mon[:3].upper())
        if not month:
            continue
        yr = int(year)
        if yr < 100:
            yr += 2000
        try:
            parsed.append(datetime(yr, month, int(day)).strftime("%Y-%m-%d"))
        except ValueError:
            pass
    return parsed


def parse_section_rows(text: str, game_type: int, is_section_expired: bool, seen_codes: set) -> List[Dict[str, Any]]:
    """Parses individual rows from wikitext table, computing anchor-based dates."""
    config = GAMES_CONFIG[game_type]
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = re.split(r'\{\{(?:Code Row|Redemption Code Row)|\n\|-', text, flags=re.IGNORECASE)
    results = []

    for row in rows:
        found_code = extract_code_from_row(row)
        if not found_code or found_code in seen_codes:
            continue

        seen_codes.add(found_code)
        desc_ru, desc_en, reward_types = parse_rewards_from_text(row, game_type)

        dates = extract_row_dates(row)
        row_lower = row.lower()

        # Stream detection: requires explicit stream indicators or 1-2 day lifespan
        is_stream = False
        if any(k in row_lower for k in ("special program", "livestream", "program code", "stream code", "preview stream")):
            is_stream = True
        elif len(dates) >= 2:
            try:
                d_start = datetime.strptime(dates[0], "%Y-%m-%d")
                d_end = datetime.strptime(dates[-1], "%Y-%m-%d")
                if 0 <= (d_end - d_start).days <= 2 and config["primary_reward"] in reward_types:
                    is_stream = True
            except Exception:
                pass

        # Expiration determination
        is_expired = is_section_expired
        expires_at = None
        created_at = f"{dates[0]}T12:00:00Z" if dates else (None if is_section_expired else now_iso)

        if is_section_expired:
            is_expired = True
            if len(dates) >= 2:
                expires_at = f"{dates[-1]}T23:59:59Z"
            elif dates:
                expires_at = f"{dates[0]}T23:59:59Z"
            else:
                expires_at = None
        else:
            # Active section parsing
            if len(dates) >= 2:
                exp_date_str = dates[-1]
                expires_at = f"{exp_date_str}T23:59:59Z"
                try:
                    exp_dt = datetime.strptime(exp_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
                    if now > exp_dt:
                        is_expired = True
                except Exception:
                    pass
            elif is_stream:
                if dates:
                    try:
                        disc_dt = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=12)
                        if now > (disc_dt + timedelta(hours=30)):
                            is_expired = True
                    except Exception:
                        pass
            else:
                if dates:
                    try:
                        disc_dt = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=12)
                        if "indef" not in row_lower and (now - disc_dt).days >= 45:
                            is_expired = True
                    except Exception:
                        pass

        status = "EXPIRED" if is_expired else ("STREAM" if is_stream else "ACTIVE")
        is_active = not is_expired

        results.append({
            "id": f"scraped_{game_type}_{found_code.lower()}",
            "game_type": game_type,
            "code": found_code,
            "rewards_description_ru": desc_ru,
            "rewards_description_en": desc_en,
            "reward_types": reward_types,
            "status": status,
            "expires_at": expires_at,
            "expiry_confidence": "estimated" if expires_at else "unknown",
            "created_at": created_at,
            "source_url": extract_source_url(row),
            "is_stream": is_stream,
            "is_active": is_active
        })

    return results


def parse_game_promocodes(game_type: int) -> List[Dict[str, Any]]:
    """Fetches and parses active & expired codes for a specific game."""
    config = GAMES_CONFIG.get(game_type)
    if not config:
        return []

    wikitext = fetch_page_wikitext(config["wiki"], config["page"])
    if not wikitext:
        return []

    active_text, expired_text = split_active_and_expired(wikitext, game_type)
    seen_codes = set()

    active_items = parse_section_rows(active_text, game_type, is_section_expired=False, seen_codes=seen_codes)
    expired_items = parse_section_rows(expired_text, game_type, is_section_expired=True, seen_codes=seen_codes)

    total_items = active_items + expired_items
    print(f"[Parser] Extracted {len(active_items)} active and {len(expired_items)} expired codes for {config['name']}")
    return total_items


def parse_all_games() -> List[Dict[str, Any]]:
    """Runs scrapers for Genshin, HSR, ZZZ, and HI3 with isolated exception safety."""
    all_codes = []
    for g_type in [0, 1, 2, 3]:
        try:
            codes = parse_game_promocodes(g_type)
            all_codes.extend(codes)
        except Exception as e:
            print(f"[Parser] Error scraping game {g_type}: {e}")
    return all_codes


if __name__ == "__main__":
    codes = parse_all_games()
    print(f"Total codes parsed: {len(codes)}")
    for c in codes[:10]:
        print(f"[{c['game_type']}] {c['code']} -> {c['status']} (expires: {c['expires_at']})")
