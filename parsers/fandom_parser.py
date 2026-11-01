#!/usr/bin/env python3
"""
Fandom MediaWiki API Parser for HoYoverse Games (Genshin, HSR, ZZZ, HI3)
Extracts active and stream promo codes without external dependencies.
"""

import re
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

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
DISALLOWED_CODES = {
    "CODE", "PROMOCODE", "ITEM", "YES", "NO", "REWARDS", "GLOBAL",
    "ONLINE", "WEBSITE", "SERVER", "NOTES", "DURATION", "EXCHANGE",
    "REDEMPTION", "DATE", "EXPIRY", "DISCOVERY", "UNKNOWN"
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
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointDataHub/1.0"}
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


def extract_active_wikitext(full_text: str, game_type: int) -> str:
    """Isolates active codes section by trimming past expired headers and comments."""
    if game_type == 0:
        match = re.search(r'==+\s*(?:Expired|Past|Inactive|History|Previous)', full_text, re.IGNORECASE)
        if match:
            full_text = full_text[:match.start()]
    elif game_type in (1, 2):
        exp_match = re.search(r'<!--\s*expired\s*-->', full_text, re.IGNORECASE)
        if exp_match:
            full_text = full_text[:exp_match.start()]
        h_match = re.search(r'==+\s*(?:Expired|Past|Inactive|History|Previous|Notes|References)', full_text, re.IGNORECASE)
        if h_match:
            full_text = full_text[:h_match.start()]
    elif game_type == 3:
        match = re.search(r'==+\s*(?:Legacy|Expired|Past|Inactive|History|Previous|Old)', full_text, re.IGNORECASE)
        if match:
            full_text = full_text[:match.start()]

    # Strip author instructions blocks
    full_text = re.sub(r'<!--\s*To add to this list[\s\S]*?-->', '', full_text, flags=re.IGNORECASE)
    return full_text


def parse_rewards_from_text(row_text: str, game_type: int) -> tuple[str, str, str, list[str]]:
    """Analyzes table row text to determine reward types, RU/EN descriptions."""
    config = GAMES_CONFIG[game_type]
    reward_types = []
    ru_parts = []
    en_parts = []

    # 1. Primary currency: Primogems / Stellar Jade / Polychromes / Crystals
    prim_match = re.search(r'(?:Primogem|Stellar Jade|Polychrome|Crystal)s?\s*(?:x|\*)\s*(\d+)', row_text, re.IGNORECASE)
    if not prim_match:
        prim_match = re.search(r'(\d+)\s*(?:\[\[)?(?:Primogem|Stellar Jade|Polychrome|Crystal)', row_text, re.IGNORECASE)
    if not prim_match:
        prim_match = re.search(r'{{(?:Item\|)?(?:Primogem|Stellar Jade|Polychrome|Crystal)[^}]*?(?:quantity|x)\s*=\s*(\d+)', row_text, re.IGNORECASE)

    if prim_match:
        amount = prim_match.group(1)
        reward_types.append(config["primary_reward"])
        ru_parts.append(f"{amount} {config['primary_name_ru']}")
        en_parts.append(f"{amount} {config['primary_name_en']}")

    # 2. Secondary currency: Mora / Credits / Dennies / Coins
    sec_match = re.search(r'(?:Mora|Credit|Dennie|Denny|Coin)s?\s*(?:x|\*)\s*([\d,]+)', row_text, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'([\d,]+)\s*(?:\[\[)?(?:Mora|Credit|Dennie|Denny|Coin)', row_text, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'{{(?:Item\|)?(?:Mora|Credit|Dennie|Denny|Coin)[^}]*?(?:quantity|x)\s*=\s*([\d,]+)', row_text, re.IGNORECASE)

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
    exp_match = re.search(r'(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)\s*(?:x|\*)\s*(\d+)', row_text, re.IGNORECASE)
    if not exp_match:
        exp_match = re.search(r'(\d+)\s*(?:\[\[)?(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)', row_text, re.IGNORECASE)

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
        ast_match = re.search(r'Asterite\s*(?:x|\*)\s*([\d,]+)', row_text, re.IGNORECASE)
    if ast_match:
        amount = ast_match.group(1).replace(",", "")
        reward_types.append("ASTERITE")
        ru_parts.append(f"{amount} Астерита")
        en_parts.append(f"{amount} Asterite")

    if not ru_parts:
        return "Внутриигровые награды", "Внутриигровые награды", "In-game Rewards", reward_types or [config["primary_reward"]]

    desc_ru = ", ".join(ru_parts)
    desc_en = ", ".join(en_parts)
    return desc_ru, desc_ru, desc_en, reward_types


def parse_game_promocodes(game_type: int) -> List[Dict[str, Any]]:
    """Fetches and parses active codes for a specific game."""
    config = GAMES_CONFIG.get(game_type)
    if not config:
        return []

    wikitext = fetch_page_wikitext(config["wiki"], config["page"])
    if not wikitext:
        return []

    active_text = extract_active_wikitext(wikitext, game_type)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Split into entries
    rows = re.split(r'\{\{(?:Code Row|Redemption Code Row)|\n\|-', active_text)
    results = []
    seen_codes = set()

    for row in rows:
        found_code = None

        # Pattern 1: Template first parameter |CODE| or |CODE\n
        template_match = re.search(r'(?:^\s*(?:<!--.*?-->)?\s*\|\s*|\|(?:\'\'\')?)([A-Za-z0-9_-]{4,30})(?:\'\'\')?\s*\|', row)
        if template_match:
            candidate = template_match.group(1).strip().upper()
            if CODE_RE.match(candidate) and not DATE_PATTERN.match(candidate) and candidate not in DISALLOWED_CODES:
                found_code = candidate

        # Pattern 2: Bold code (e.g. HI3 tables: |'''CODE'''||)
        if not found_code:
            bold_match = re.search(r"'''([A-Z0-9_-]{4,25})'''", row)
            if bold_match:
                candidate = bold_match.group(1).strip().upper()
                if CODE_RE.match(candidate) and not DATE_PATTERN.match(candidate) and candidate not in DISALLOWED_CODES:
                    found_code = candidate

        # Pattern 3: URL code fallback
        if not found_code:
            url_match = re.search(r'(?:gift|redemption)\?(?:[^\s"\'<>]*&)?code=([A-Za-z0-9_-]{3,30})', row, re.IGNORECASE)
            if url_match:
                candidate = url_match.group(1).strip().upper()
                if CODE_RE.match(candidate) and candidate not in DISALLOWED_CODES:
                    found_code = candidate

        if not found_code or found_code in seen_codes:
            continue

        seen_codes.add(found_code)

        desc, desc_ru, desc_en, reward_types = parse_rewards_from_text(row, game_type)

        # Check stream indicators
        is_stream = False
        if config["primary_reward"] in reward_types and ("100" in desc or "300" in desc):
            is_stream = True
        if "special_program" in row.lower() or "livestream" in row.lower() or "stream" in row.lower():
            is_stream = True

        # Extract dates from row
        dates = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', row)
        expiry_date = None
        if len(dates) >= 2:
            expiry_date = dates[-1]
            try:
                d_start = datetime.strptime(dates[0], "%Y-%m-%d")
                d_end = datetime.strptime(dates[-1], "%Y-%m-%d")
                if (d_end - d_start).days <= 3:
                    is_stream = True
            except Exception:
                pass
        elif len(dates) == 1 and "indef" not in row.lower() and "unknown" not in row.lower():
            if is_stream:
                expiry_date = dates[0]

        if expiry_date:
            expires_at = f"{expiry_date}T23:59:59Z"
            try:
                exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
                is_expired = exp_dt < datetime.now(timezone.utc)
            except Exception:
                is_expired = False
        else:
            is_expired = False
            expires_at = (
                (datetime.now(timezone.utc) + timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
                if is_stream
                else (datetime.now(timezone.utc) + timedelta(days=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
            )

        if is_stream and dates:
            try:
                disc_dt = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - disc_dt).days >= 2:
                    is_expired = True
            except Exception:
                pass
        elif not is_stream and dates:
            try:
                disc_dt = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if "indef" not in row.lower() and (datetime.now(timezone.utc) - disc_dt).days >= 45:
                    is_expired = True
            except Exception:
                pass

        if is_expired:
            continue

        status = "STREAM" if is_stream else "ACTIVE"
        is_active = True

        results.append({
            "id": f"scraped_{game_type}_{found_code.lower()}",
            "game_type": game_type,
            "code": found_code,
            "rewards_description": desc,
            "rewards_description_ru": desc_ru,
            "rewards_description_en": desc_en,
            "reward_types": reward_types,
            "status": status,
            "expires_at": expires_at,
            "created_at": f"{dates[0]}T12:00:00Z" if dates else now_iso,
            "is_stream": is_stream,
            "is_active": is_active
        })

    print(f"[Parser] Extracted {len(results)} active codes for {config['name']}")
    return results


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
    print(f"Total codes found: {len(codes)}")
    for c in codes:
        print(f"[{c['game_type']}] {c['code']} -> {c['rewards_description']}")
