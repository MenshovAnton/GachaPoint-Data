#!/usr/bin/env python3
"""
GachaPoint Data Hub — Autonomous New Entity Ingestion Tool
Allows adding a new character, weapon, or bangboo across any of the 4 games:
1. Fetches official in-game square icon / render from Fandom MediaWiki API via curl.
2. Converts/normalizes to 256x256 (or 512x512) RGBA PNG.
3. Appends or updates the entry in game_catalog.json with bilingual names and aliases.
4. Automatically runs lint_data.py to ensure zero warnings or errors.
"""

import os
import sys
import json
import argparse
import subprocess
import urllib.request
import urllib.parse
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")

WIKI_CONFIG = {
    0: {"name": "Genshin Impact", "wiki": "genshin-impact", "subdir": "0", "target_size": (256, 256)},
    1: {"name": "Honkai: Star Rail", "wiki": "honkai-star-rail", "subdir": "1", "target_size": (256, 256)},
    2: {"name": "Zenless Zone Zero", "wiki": "zenless-zone-zero", "subdir": "2", "target_size": (256, 256)},
    3: {"name": "Honkai Impact 3rd", "wiki": "honkaiimpact3", "subdir": "3", "target_size": (256, 256)}
}

def slugify(text: str) -> str:
    s = text.strip().lower()
    s = s.replace(":", " ").replace("-", " ").replace("'", "").replace("\"", "")
    s = "_".join(s.split())
    return s

def fetch_fandom_image_url(wiki: str, candidate_titles: list) -> tuple:
    api_url = f"https://{wiki}.fandom.com/api.php"
    data = urllib.parse.urlencode({
        "action": "query",
        "prop": "imageinfo",
        "iiprop": "url",
        "titles": "|".join(candidate_titles),
        "format": "json"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        pages = res.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title")
            ii = page.get("imageinfo")
            if ii and "url" in ii[0]:
                return title, ii[0]["url"]
    return None, None

def download_and_format_avatar(wiki: str, url: str, dest_path: str, target_size: tuple):
    temp_file = dest_path + ".tmp"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"https://{wiki}.fandom.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        with open(temp_file, "wb") as file:
            file.write(response.read())

    try:
        im = Image.open(temp_file).convert("RGBA")
        if im.size != target_size:
            im = im.resize(target_size, Image.Resampling.LANCZOS)
        im.save(dest_path, format="PNG", optimize=True)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

def add_catalog_entity(game_type: int, name_ru: str, name_en: str, rarity: str, item_type: str, is_standard: bool, aliases: list = None, custom_file: str = None):
    cfg = WIKI_CONFIG[game_type]
    file_stem = custom_file or (slugify(name_en) + ".png")
    sub_map = {"CHARACTER": "characters", "WEAPON": "weapons", "BANGBOO": "bangboo", "ELF": "elves", "ASTRAL_OP": "astral_ops"}
    subfolder = sub_map.get(item_type, "characters")
    dest_dir = os.path.join(BASE_DIR, "avatars", cfg["subdir"], subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file_stem)
    
    print(f"[{cfg['name']}] Processing {name_ru} / {name_en} ({rarity}, {item_type})...")
    
    # 1. Search image candidates on Fandom
    candidates = []
    if game_type == 0: # Genshin
        if item_type == "CHARACTER":
            candidates = [f"File:{name_en} Icon.png", f"File:Character {name_en} Icon.png"]
        elif item_type == "WEAPON":
            candidates = [f"File:Weapon {name_en}.png", f"File:Weapon {name_en} 2nd.png"]
    elif game_type == 1: # HSR
        if item_type == "CHARACTER":
            candidates = [f"File:Character {name_en} Icon.png", f"File:{name_en} Icon.png"]
        elif item_type == "WEAPON":
            candidates = [f"File:Light Cone {name_en}.png", f"File:{name_en}.png"]
    elif game_type == 2: # ZZZ
        if item_type == "CHARACTER":
            candidates = [f"File:Agent {name_en} Icon.png", f"File:{name_en} Icon.png"]
        elif item_type == "BANGBOO":
            candidates = [f"File:Bangboo {name_en} Icon.png", f"File:{name_en} Icon.png"]
        elif item_type == "WEAPON":
            candidates = [f"File:W-Engine {name_en} Icon.png", f"File:{name_en} Icon.png"]
    elif game_type == 3: # HI3
        if item_type == "CHARACTER":
            candidates = [f"File:{name_en} (Icon).png", f"File:{name_en} (Bust).png", f"File:{name_en}.png"]
        elif item_type in ["BANGBOO", "ELF"]:
            candidates = [f"File:{name_en} (Icon).png", f"File:{name_en}.png"]
        elif item_type == "WEAPON":
            candidates = [f"File:{name_en} (6).png", f"File:{name_en} (5).png", f"File:{name_en} (Icon).png"]
            
    matched_title, img_url = fetch_fandom_image_url(cfg["wiki"], candidates)
    if not img_url:
        print(f"Warning: Could not find candidate images for {name_en} on {cfg['wiki']}. Candidates: {candidates}")
        if not os.path.exists(dest_path):
            print(f"Notice: Image file does not exist locally ({dest_path}). App will show dynamic letter badge until image is loaded.")
    else:
        print(f"Found image: {matched_title} -> {img_url}")
        download_and_format_avatar(cfg["wiki"], img_url, dest_path, cfg["target_size"])
        print(f"Saved avatar: {dest_path} ({os.path.getsize(dest_path)} bytes)")

    # 2. Update game_catalog.json
    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)
        
    icon_path = f"avatars/{cfg['subdir']}/{subfolder}/{file_stem}"
    all_aliases = list(set([name_ru, name_en] + (aliases or [])))
    
    target_game = None
    for g in catalog.get("games", []):
        if g.get("game_type") == game_type:
            target_game = g
            break
            
    if target_game is None:
        raise ValueError(f"Game type {game_type} not found in catalog")
        
    # Check if item exists
    updated = False
    for it in target_game.get("items", []):
        if it.get("name_en") == name_en or it.get("name_ru") == name_ru:
            it["name_ru"] = name_ru
            it["name_en"] = name_en
            it["rarity"] = rarity
            it["type"] = item_type
            it["is_standard"] = is_standard
            it["icon_path"] = icon_path
            it["aliases"] = all_aliases
            updated = True
            print(f"Updated existing item '{name_ru}' in catalog.")
            break
            
    if not updated:
        new_item = {
            "name_ru": name_ru,
            "name_en": name_en,
            "rarity": rarity,
            "type": item_type,
            "is_standard": is_standard,
            "icon_path": icon_path,
            "aliases": all_aliases
        }
        target_game["items"].append(new_item)
        print(f"Added new item '{name_ru}' to catalog.")
        
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        
    # 3. Mirror to Android assets if present
    android_assets_catalog = os.path.join(BASE_DIR, "..", "app", "src", "main", "assets", "data", "game_catalog.json")
    if os.path.exists(os.path.dirname(android_assets_catalog)):
        with open(android_assets_catalog, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        print("Mirrored to Android assets catalog.")

    # 4. Run lint_data.py
    print("\nRunning linter verification...")
    subprocess.run([sys.executable, "-m", "scripts.tools.lint_data", "--strict"], cwd=BASE_DIR, check=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add or update a character/weapon entity in GachaPoint")
    parser.add_argument("--game", type=int, required=True, choices=[0, 1, 2, 3], help="Game ID (0: Genshin, 1: HSR, 2: ZZZ, 3: HI3)")
    parser.add_argument("--name-ru", type=str, required=True, help="Russian name (e.g. 'Скирк')")
    parser.add_argument("--name-en", type=str, required=True, help="English name (e.g. 'Skirk')")
    parser.add_argument("--rarity", type=str, default=None, choices=["3★", "4★", "5★", "S", "A", "B"], help="Rarity (default 5★ for Genshin/HSR, S for ZZZ/HI3)")
    parser.add_argument("--type", type=str, default="CHARACTER", choices=["CHARACTER", "WEAPON", "BANGBOO", "ELF", "ASTRAL_OP"], help="Item type")
    parser.add_argument("--standard", action="store_true", help="Is standard banner item")
    parser.add_argument("--aliases", nargs="*", default=[], help="Additional search aliases")
    parser.add_argument("--file", type=str, default=None, help="Custom icon filename")
    
    args = parser.parse_args()
    rarity = args.rarity or ("5★" if args.game in (0, 1) else "S")

    add_catalog_entity(
        game_type=args.game,
        name_ru=args.name_ru,
        name_en=args.name_en,
        rarity=rarity,
        item_type=args.type,
        is_standard=args.standard,
        aliases=args.aliases,
        custom_file=args.file
    )
