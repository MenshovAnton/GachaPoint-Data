#!/usr/bin/env python3
"""
ZZZ Autonomous HD Asset Downloader (using curl.exe & MediaWiki API)
Downloads master-quality PNGs directly from Fandom with zero Cloudflare blocks.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import subprocess
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")
DEST_DIR = os.path.join(BASE_DIR, "avatars", "2")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

def get_fandom_image_url(title: str) -> Optional[str]:
    api_url = "https://zenless-zone-zero.fandom.com/api.php"
    params = {
        "action": "query",
        "titles": f"File:{title}",
        "prop": "imageinfo",
        "iiprop": "url",
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
                    raw_url = pdata["imageinfo"][0].get("url", "")
                    if raw_url:
                        # Append format=original
                        if "&format=original" not in raw_url:
                            sep = "&" if "?" in raw_url else "?"
                            return f"{raw_url}{sep}format=original"
                        return raw_url
    except Exception as e:
        pass
    return None

def curl_download(url: str, dest_file: str) -> bool:
    cmd = [
        "curl.exe", "-s", url,
        "-H", f"User-Agent: {USER_AGENT}",
        "-H", "Referer: https://zenless-zone-zero.fandom.com/",
        "-o", dest_file
    ]
    try:
        subprocess.run(cmd, check=True, timeout=30)
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 2000:
            # Verify PNG or WEBP header
            with open(dest_file, "rb") as f:
                header = f.read(16)
                if b"PNG" in header or b"WEBP" in header:
                    return True
        if os.path.exists(dest_file):
            os.remove(dest_file)
    except Exception as e:
        if os.path.exists(dest_file):
            os.remove(dest_file)
    return False

def main():
    print("=== Downloading ZZZ Master Assets (Agents, Bangboo, W-Engines) ===")
    os.makedirs(DEST_DIR, exist_ok=True)

    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    g2 = next((g for g in catalog["games"] if g["game_type"] == 2), None)
    if not g2:
        return

    items = g2.get("items", [])
    total = len(items)
    success = 0

    for idx, item in enumerate(items):
        itype = item.get("type")
        n_en = item.get("name_en", "").strip()
        n_ru = item.get("name_ru", item.get("name", ""))
        icon_url = item.get("icon_url", "")
        filename = os.path.basename(icon_url)
        master_dest = os.path.join(DEST_DIR, f"{filename}.master.png")

        print(f"[{idx+1}/{total}] Searching master art for {itype} {n_ru} ({n_en})...")

        title_candidates = []
        if itype == "BANGBOO":
            title_candidates = [
                f"{n_en} Portrait.png",
                f"{n_en} Gacha Artwork.png",
                f"Bangboo {n_en} Icon.png",
                f"Item {n_en}.png",
                f"Bangboo {n_en}.png"
            ]
        elif itype == "WEAPON":
            title_candidates = [
                f"W-Engine {n_en}.png",
                f"Item {n_en}.png",
                f"{n_en}.png"
            ]
        elif itype == "CHARACTER":
            title_candidates = [
                f"Agent {n_en} Icon.png",
                f"{n_en} Portrait.png",
                f"{n_en} Icon.png",
                f"Agent {n_en}.png"
            ]

        found = False
        for title in title_candidates:
            img_url = get_fandom_image_url(title)
            if img_url:
                if curl_download(img_url, master_dest):
                    print(f" [+] Downloaded master art: {title} -> {filename} ({os.path.getsize(master_dest)} bytes)")
                    success += 1
                    found = True
                    break

        if not found:
            print(f" [-] Could not find master art for {n_en}")

    print(f"\nZZZ Master download complete: {success}/{total} assets downloaded.")

if __name__ == "__main__":
    main()
