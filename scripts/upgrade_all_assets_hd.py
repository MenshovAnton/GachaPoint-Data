#!/usr/bin/env python3
"""
GachaPoint Data Hub — All-Inclusive HD Asset Pipeline (512x512)
Upgrades:
1. HSR Characters: master portraits from Mar-7th/StarRailRes (2048x2048 -> 512x512)
2. HSR Light Cones: master card art from StarRailRes (902x1260 -> 512x512 inner art, no borders)
3. ZZZ Agents: full-resolution original icons & portraits from ZZZ Wiki/Hakushin (512x512)
4. ZZZ Bangboo: master 1536x1728 portraits centered in 512x512 transparent canvas
5. ZZZ W-Engines: master 3D orb renders centered in 512x512 transparent canvas
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

STARRAILRES_BASE = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

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
                # Verify not Cloudflare challenge
                if data[:15].startswith(b"<!DOCTYPE html>") or data[:15].startswith(b"<html"):
                    return None
                return data
    except Exception as e:
        return None
    return None

def get_fandom_image_url(wiki: str, title: str) -> Optional[str]:
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
                    raw_url = pdata["imageinfo"][0].get("url", "")
                    if raw_url:
                        # Append format=original for lossless PNG
                        base = raw_url.split("?")[0]
                        if "/revision" not in base:
                            base = base + "/revision/latest"
                        return f"{base}?format=original"
    except Exception as e:
        pass
    return None

def upgrade_hsr_light_cones():
    print("\n--- Upgrading HSR Light Cones to Master 512x512 ---")
    lcs_index = fetch_json(f"{STARRAILRES_BASE}/index_new/en/light_cones.json")
    if not lcs_index:
        print(" [!] Failed to fetch StarRailRes light cones index.")
        return

    name_to_id = {}
    for lcid, lc in lcs_index.items():
        name = lc.get("name", "").strip().lower()
        name_to_id[name] = (lcid, lc)

    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    g1 = next((g for g in catalog["games"] if g["game_type"] == 1), None)
    if not g1:
        return

    dest_dir = os.path.join(AVATARS_DIR, "1")
    count = 0

    for item in g1.get("items", []):
        if item.get("type") != "WEAPON":
            continue
        n_en = item.get("name_en", "").strip().lower()
        icon_url = item.get("icon_url", "")
        filename = os.path.basename(icon_url)
        dest_path = os.path.join(dest_dir, filename)

        match = name_to_id.get(n_en)
        if not match:
            # Substring match
            for k, val in name_to_id.items():
                if k in n_en or n_en in k:
                    match = val
                    break

        if match:
            lcid, lc = match
            portrait_path = lc.get("portrait", f"image/light_cone_portrait/{lcid}.png")
            direct_url = f"{STARRAILRES_BASE}/{portrait_path}"
            print(f"Downloading master art for {item.get('name_ru')}: {direct_url}...")
            raw_bytes = fetch_bytes(direct_url)
            if raw_bytes and len(raw_bytes) > 20000:
                tmp_raw = dest_path + ".master.png"
                with open(tmp_raw, "wb") as f_out:
                    f_out.write(raw_bytes)
                count += 1
                print(f" [+] Fetched master portrait for {filename} ({len(raw_bytes)} bytes)")
            else:
                print(f" [-] Failed to download {direct_url}")

    print(f"HSR Light Cones downloaded: {count}")

def upgrade_zzz_assets():
    print("\n--- Upgrading ZZZ Bangboo & W-Engines & Agents ---")
    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    g2 = next((g for g in catalog["games"] if g["game_type"] == 2), None)
    if not g2:
        return

    dest_dir = os.path.join(AVATARS_DIR, "2")
    count = 0

    for item in g2.get("items", []):
        itype = item.get("type")
        n_en = item.get("name_en", "").strip()
        icon_url = item.get("icon_url", "")
        filename = os.path.basename(icon_url)
        dest_path = os.path.join(dest_dir, filename)

        title_candidates = []
        if itype == "BANGBOO":
            title_candidates = [
                f"{n_en} Portrait.png",
                f"{n_en} Gacha Artwork.png",
                f"Bangboo {n_en} Icon.png",
                f"Item {n_en}.png"
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
                f"{n_en} Icon.png"
            ]

        for cand in title_candidates:
            url = get_fandom_image_url("zenless-zone-zero", cand)
            if url:
                print(f"Downloading {itype} {n_en} from {cand}...")
                raw_bytes = fetch_bytes(url)
                if raw_bytes and len(raw_bytes) > 5000:
                    tmp = dest_path + ".master.png"
                    with open(tmp, "wb") as f_out:
                        f_out.write(raw_bytes)
                    count += 1
                    print(f" [+] Saved master {cand} ({len(raw_bytes)} bytes)")
                    break

    print(f"ZZZ Master assets downloaded: {count}")

if __name__ == "__main__":
    upgrade_hsr_light_cones()
    upgrade_zzz_assets()
