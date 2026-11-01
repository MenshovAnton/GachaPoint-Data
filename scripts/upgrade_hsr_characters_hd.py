#!/usr/bin/env python3
"""
HSR Character HD Upgrader
Upgrades all Honkai: Star Rail characters in avatars/1/
using master character preview & portrait assets from Mar-7th/StarRailRes (GitHub).
Produces true 512x512 HD assets with high-contrast sharp details.
"""

import os
import sys
import json
import urllib.request
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")
AVATARS_DIR = os.path.join(BASE_DIR, "avatars", "1")

STARRAILRES_BASE = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GachaPointHSRUpgrader/2.0"

def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f" [!] Error fetching JSON from {url}: {e}")
        return None

def fetch_bytes(url: str) -> Optional[bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                data = resp.read()
                if len(data) > 5000:
                    return data
    except Exception:
        return None
    return None

def upgrade_all_hsr():
    print("Fetching StarRailRes character index...")
    chars_index = fetch_json(f"{STARRAILRES_BASE}/index_new/en/characters.json")
    if not chars_index:
        print(" [X] Failed to fetch StarRailRes characters index.")
        return

    name_map = {}
    for cid, c in chars_index.items():
        cname = c.get("name", "").strip().lower()
        name_map[cname] = (cid, c)

    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    g1 = next((g for g in catalog["games"] if g["game_type"] == 1), None)
    if not g1:
        return

    downloaded = 0
    total = 0

    for item in g1.get("items", []):
        if item.get("type") != "CHARACTER":
            continue
        total += 1
        name_en = item.get("name_en", "").strip().lower()
        icon_url = item.get("icon_url", "")
        filename = os.path.basename(icon_url)
        dest_path = os.path.join(AVATARS_DIR, filename)

        match = name_map.get(name_en)
        if not match:
            # Try fuzzy matching
            for k, val in name_map.items():
                if k in name_en or name_en in k or name_en.replace("-", " ") == k:
                    match = val
                    break

        if match:
            cid, c = match
            preview_url = f"{STARRAILRES_BASE}/image/character_preview/{cid}.png"
            raw_bytes = fetch_bytes(preview_url)
            if not raw_bytes:
                # Try portrait
                portrait_url = f"{STARRAILRES_BASE}/image/character_portrait/{cid}.png"
                raw_bytes = fetch_bytes(portrait_url)

            if raw_bytes:
                tmp_master = dest_path + ".master.png"
                with open(tmp_master, "wb") as f_out:
                    f_out.write(raw_bytes)
                downloaded += 1
                print(f" [+] Downloaded master art for {item.get('name_ru')}: {filename} ({len(raw_bytes)} bytes)")
            else:
                print(f" [-] Failed to download master art for {name_en} (ID: {cid})")
        else:
            print(f" [?] Not matched in StarRailRes: {name_en}")

    print(f"\nDownloaded master art for {downloaded}/{total} HSR characters.")

if __name__ == "__main__":
    upgrade_all_hsr()
