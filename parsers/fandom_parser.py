#!/usr/bin/env python3
"""
Fandom MediaWiki API Parser for HoYoverse Games (Genshin, HSR, ZZZ)
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
URL_CODE_RE = re.compile(r'(?:gift|redemption)\?(?:[^\s"\'<>]*&)?code=([A-Za-z0-9_-]{3,30})', re.IGNORECASE)
TAG_CODE_RE = re.compile(r'<code>([A-Za-z0-9_-]{3,30})</code>', re.IGNORECASE)
PARAM_CODE_RE = re.compile(r'\|\s*code\s*=\s*([A-Za-z0-9_-]{3,30})', re.IGNORECASE)
BOLD_CODE_RE = re.compile(r"'''([A-Z0-9_-]{4,25})'''")


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


def extract_active_wikitext(full_text: str) -> str:
    """Isolates active codes section by trimming everything past the Expired header."""
    split_match = re.search(r'==+\s*(?:Expired|Past|Inactive|History|Previous)', full_text, re.IGNORECASE)
    if split_match:
        return full_text[:split_match.start()]
    return full_text


def parse_rewards_from_text(row_text: str, game_type: int) -> tuple[str, str, str, list[str]]:
    """Analyzes table row text to determine reward types, RU/EN descriptions."""
    config = GAMES_CONFIG[game_type]
    reward_types = []
    ru_parts = []
    en_parts = []

    # 1. Primary currency: Primogems / Stellar Jade / Polychromes / Crystals
    prim_match = re.search(r'(\d+)\s*(?:\[\[)?(?:Primogem|Stellar Jade|Polychrome|Crystal)', row_text, re.IGNORECASE)
    if not prim_match:
        prim_match = re.search(r'{{(?:Item\|)?(?:Primogem|Stellar Jade|Polychrome|Crystal)[^}]*?x\s*=\s*(\d+)', row_text, re.IGNORECASE)

    if prim_match:
        amount = prim_match.group(1)
        reward_types.append(config["primary_reward"])
        ru_parts.append(f"{amount} {config['primary_name_ru']}")
        en_parts.append(f"{amount} {config['primary_name_en']}")

    # 2. Secondary currency: Mora / Credits / Dennies / Coins
    sec_match = re.search(r'(\d[\d\s,]*\d|\d+)\s*(?:\[\[)?(?:Mora|Credit|Dennie|Coin)', row_text, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'{{(?:Item\|)?(?:Mora|Credit|Dennie|Coin)[^}]*?x\s*=\s*(\d[\d\s,]*\d|\d+)', row_text, re.IGNORECASE)

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

    # 3. EXP and Materials (Hero's Wit, Traveler's Guide, Investigator Log, Asterite)
    exp_match = re.search(r'(\d+)\s*(?:\[\[)?(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)', row_text, re.IGNORECASE)
    if not exp_match:
        exp_match = re.search(r'{{(?:Item\|)?(?:Hero\'s Wit|Traveler\'s Guide|Investigator Log|Adventurer\'s Experience)[^}]*?x\s*=\s*(\d+)', row_text, re.IGNORECASE)

    if exp_match:
        amount = exp_match.group(1)
        reward_types.append("EXP")
        is_adv = "adventurer" in row_text.lower()
        exp_ru = "Опыта искателя" if is_adv else "Опыта героя" if game_type == 0 else "Путеводителей" if game_type == 1 else "Журналов" if game_type == 2 else "Опыта"
        exp_en = "Adventurer's Exp" if is_adv else "Hero's Wit" if game_type == 0 else "Traveler's Guides" if game_type == 1 else "Investigator Logs" if game_type == 2 else "EXP"
        ru_parts.append(f"{amount} {exp_ru}")
        en_parts.append(f"{amount} {exp_en}")

    ast_match = re.search(r'(\d[\d\s,]*\d|\d+)\s*(?:\[\[)?(?:Asterite)', row_text, re.IGNORECASE)
    if ast_match:
        amount = ast_match.group(1)
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

    active_text = extract_active_wikitext(wikitext)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Split into rows/entries
    rows = re.split(r'\n\|-|\n\n', active_text)
    results = []
    seen_codes = set()

    for row in rows:
        # Find candidate code
        found_code = None
        for pattern in [URL_CODE_RE, TAG_CODE_RE, PARAM_CODE_RE, BOLD_CODE_RE]:
            match = pattern.search(row)
            if match:
                candidate = match.group(1).strip().upper()
                if CODE_RE.match(candidate):
                    found_code = candidate
                    break

        if not found_code or found_code in seen_codes:
            continue

        # Ignore template header titles or obvious false positives
        if found_code in {"CODE", "PROMOCODE", "REDEMPTION", "REWARDS", "DURATION", "ITEM", "YES", "NO"}:
            continue

        seen_codes.add(found_code)

        desc, desc_ru, desc_en, reward_types = parse_rewards_from_text(row, game_type)

        # Check stream indicators
        is_stream = False
        if "stream" in row.lower() or "special program" in row.lower() or "100" in desc:
            # 100 primary currency is characteristic of livestream codes
            if config["primary_reward"] in reward_types and "100" in desc:
                is_stream = True

        status = "STREAM" if is_stream else "ACTIVE"
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ") if is_stream else (datetime.now(timezone.utc) + timedelta(days=25)).strftime("%Y-%m-%dT%H:%M:%SZ")

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
            "created_at": now_iso,
            "is_stream": is_stream,
            "is_active": True
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
