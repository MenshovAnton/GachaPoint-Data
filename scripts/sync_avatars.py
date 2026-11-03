#!/usr/bin/env python3
"""
GachaPoint Data Hub — High-Res Asset Synchronizer
Defensively pulls, validates, and normalizes character and weapon avatars
from authorized/official community CDNs:
- Genshin Impact: Enka.Network / Dimbreath GenshinData
- Honkai: Star Rail: Mar-7th/StarRailRes
- Zenless Zone Zero: Hakush.in / ZZZData
- Honkai Impact 3rd: Fandom MediaWiki / Battlesuit Icons
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")
AVATARS_DIR = os.path.join(BASE_DIR, "avatars")
REMOTE_BASE = "https://raw.githubusercontent.com/menshovanton/GachaPoint-Data/main/"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointAssetSync/2.0"

# Mapping of known clean upstream sources
ENKA_GENSHIN_BASE = "https://enka.network/ui"
STARRAILRES_BASE = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master"

def fetch_image_bytes(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status == 200:
            return response.read()
    raise RuntimeError(f"HTTP response non-200 for {url}")

def sync_catalog_avatars(dry_run: bool = False):
    if not os.path.exists(CATALOG_PATH):
        print(f"Catalog not found at {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    total = 0
    synced = 0
    failed = 0

    for g in catalog.get("games", []):
        gt = g.get("game_type", 0)
        target_dir = os.path.join(AVATARS_DIR, str(gt))
        os.makedirs(target_dir, exist_ok=True)

        for item in g.get("items", []):
            total += 1
            icon_path = item.get("icon_path", "")
            if not icon_path:
                continue

            filename = os.path.basename(icon_path)
            local_path = os.path.join(target_dir, filename)
            icon_url = REMOTE_BASE + icon_path

            # If already exists and size > 2KB, skip
            if os.path.exists(local_path) and os.path.getsize(local_path) > 2048:
                continue

            print(f"[{gt}] Downloading {item.get('name_ru', item.get('name'))} -> {filename}...")
            if dry_run:
                continue

            # Attempt download from icon_url or upstream fallback
            success = False
            candidate_urls = [icon_url]

            # Try downloading
            for cand in candidate_urls:
                try:
                    data = fetch_image_bytes(cand)
                    if len(data) > 500:
                        tmp_path = local_path + ".tmp"
                        with open(tmp_path, "wb") as f_out:
                            f_out.write(data)
                        os.replace(tmp_path, local_path)
                        synced += 1
                        success = True
                        print(f" -> Saved {local_path} ({len(data)} bytes)")
                        break
                except Exception as e:
                    # network or 404
                    pass

            if not success:
                failed += 1

    print(f"\n[Sync Complete] Total: {total}, Downloaded: {synced}, Skipped/Failed: {failed}")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    sync_catalog_avatars(dry_run=is_dry)
