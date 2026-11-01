#!/usr/bin/env python3
"""
GachaPoint Data Hub — High-Definition (512x512) Icon Upgrader
Fetches native, crystal-clear 512x512 character icons for:
- Game 1: Honkai: Star Rail (from Mar-7th/StarRailRes and HSR Fandom)
- Game 2: Zenless Zone Zero (from ZZZ Fandom and Hakush.in)
Eliminates pixelation, JPEG compression artifacts, and blurry upscaling.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")
AVATARS_DIR = os.path.join(BASE_DIR, "avatars")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointHDUpscaler/2.0"

def get_fandom_image_direct_url(wiki: str, title: str) -> Optional[str]:
    """Queries MediaWiki API for the original high-res image URL."""
    api_url = f"https://{wiki}.fandom.com/api.php"
    params = {
        "action": "query",
        "titles": f"File:{title}",
        "prop": "imageinfo",
        "iiprop": "url|size",
        "format": "json"
    }
    url = f"{api_url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                if "imageinfo" in pdata and pdata["imageinfo"]:
                    # Return original full resolution URL (strip trailing /revision/...)
                    raw_url = pdata["imageinfo"][0].get("url", "")
                    if "/revision" in raw_url:
                        return raw_url.split("/revision")[0]
                    return raw_url
    except Exception as e:
        print(f" [!] Fandom lookup failed for {title}: {e}")
    return None

def download_file(url: str, dest_path: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                data = resp.read()
                if len(data) > 1024:
                    tmp = dest_path + ".tmp"
                    with open(tmp, "wb") as f:
                        f.write(data)
                    os.replace(tmp, dest_path)
                    return True
    except Exception as e:
        print(f" [X] Download error from {url}: {e}")
    return False

def upgrade_hsr_icons():
    print("\n--- Upgrading Honkai: Star Rail Icons (Game 1) ---")
    dest_dir = os.path.join(AVATARS_DIR, "1")
    os.makedirs(dest_dir, exist_ok=True)

    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    g1 = next((g for g in catalog["games"] if g["game_type"] == 1), None)
    if not g1:
        return

    success = 0
    total = 0

    for item in g1.get("items", []):
        if item.get("type") != "CHARACTER":
            continue
        total += 1
        name_en = item.get("name_en", "")
        icon_url = item.get("icon_url", "")
        filename = os.path.basename(icon_url)
        dest_file = os.path.join(dest_dir, filename)

        print(f"Fetching HD for {name_en}...")
        # HSR Fandom naming standard: Character_{Name}_Icon.png
        fandom_title = f"Character {name_en} Icon.png"
        direct_url = get_fandom_image_direct_url("honkai-star-rail", fandom_title)
        if not direct_url:
            # Fallback variations
            fandom_title = f"{name_en} Icon.png"
            direct_url = get_fandom_image_direct_url("honkai-star-rail", fandom_title)

        if direct_url:
            if download_file(direct_url, dest_file):
                print(f" [+] Upgraded {filename} to HD ({os.path.getsize(dest_file)} bytes)")
                success += 1
            else:
                print(f" [-] Failed to download {direct_url}")
        else:
            print(f" [?] Not found on Fandom: {fandom_title}")

    print(f"HSR Upgrade complete: {success}/{total} upgraded.")

def upgrade_zzz_icons():
    print("\n--- Upgrading Zenless Zone Zero Icons (Game 2) ---")
    dest_dir = os.path.join(AVATARS_DIR, "2")
    os.makedirs(dest_dir, exist_ok=True)

    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    g2 = next((g for g in catalog["games"] if g["game_type"] == 2), None)
    if not g2:
        return

    success = 0
    total = 0

    for item in g2.get("items", []):
        if item.get("type") != "CHARACTER":
            continue
        total += 1
        name_en = item.get("name_en", "")
        icon_url = item.get("icon_url", "")
        filename = os.path.basename(icon_url)
        dest_file = os.path.join(dest_dir, filename)

        print(f"Fetching HD for {name_en}...")
        # ZZZ Fandom naming standard: Agent_{Name}_Icon.png
        fandom_title = f"Agent {name_en} Icon.png"
        direct_url = get_fandom_image_direct_url("zenless-zone-zero", fandom_title)
        if not direct_url:
            fandom_title = f"{name_en} Icon.png"
            direct_url = get_fandom_image_direct_url("zenless-zone-zero", fandom_title)

        if direct_url:
            if download_file(direct_url, dest_file):
                print(f" [+] Upgraded {filename} to HD ({os.path.getsize(dest_file)} bytes)")
                success += 1
            else:
                print(f" [-] Failed to download {direct_url}")
        else:
            print(f" [?] Not found on Fandom: {fandom_title}")

    print(f"ZZZ Upgrade complete: {success}/{total} upgraded.")

if __name__ == "__main__":
    print("=== GachaPoint HD Asset Upgrader (HSR & ZZZ) ===")
    upgrade_hsr_icons()
    upgrade_zzz_icons()
