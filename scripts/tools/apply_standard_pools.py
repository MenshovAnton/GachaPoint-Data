#!/usr/bin/env python3
"""
Apply or verify the standard-pool flags in game_catalog.json.

The expected pools are stored in standard_pools.json and are matched against
catalog names and aliases. Run with --check in CI to detect drift.
"""

import argparse
import json
import os
import sys

from scripts.parsers.official_banners_parser import load_catalog_lookup, resolve_item

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")
POOLS_PATH = os.path.join(BASE_DIR, "standard_pools.json")

GROUP_MAP = {
    0: [
        ("CHARACTER", ["characters_5", "characters_4"]),
        ("WEAPON", ["weapons_5", "weapons_4"]),
    ],
    1: [
        ("CHARACTER", ["characters_5", "characters_4"]),
        ("WEAPON", ["light_cones_5", "light_cones_4"]),
    ],
    2: [
        ("CHARACTER", ["agents_S", "agents_A"]),
        ("WEAPON", ["w_engines_S", "w_engines_A"]),
        ("BANGBOO", ["bangboo_S", "bangboo_A"]),
    ],
    3: [
        ("CHARACTER", ["characters_S", "characters_other"]),
        ("WEAPON", []),
        ("ELF", []),
        ("ASTRAL_OP", []),
    ],
}


def expected_ids(pools, game_type, keys, lookup):
    target_ids = set()
    unmatched = []
    game_pools = pools.get(str(game_type), {})
    for key in keys:
        for name in game_pools.get(key, []):
            item = resolve_item(name, lookup.get(game_type, {}))
            if item:
                target_ids.add(item.get("name_en"))
            else:
                unmatched.append(name)
    return target_ids, unmatched


def apply_pools(catalog, lookup, pools, write=True):
    changed = []
    unmatched = []
    for game in catalog.get("games", []):
        game_type = int(game.get("game_type", 0))
        for item_type, keys in GROUP_MAP.get(game_type, []):
            target_ids, missing = expected_ids(pools, game_type, keys, lookup)
            unmatched.extend((game_type, item_type, name) for name in missing)
            for item in game.get("items", []):
                if item.get("type") != item_type:
                    continue
                should_be_standard = item.get("name_en") in target_ids
                if item.get("is_standard") != should_be_standard:
                    changed.append((game_type, item_type, item.get("name_en"), should_be_standard))
                    if write:
                        item["is_standard"] = should_be_standard
    return changed, unmatched


def main():
    parser = argparse.ArgumentParser(description="Apply or verify standard-pool flags")
    parser.add_argument("--check", action="store_true", help="Fail if the catalog differs from standard_pools.json")
    args = parser.parse_args()

    with open(POOLS_PATH, "r", encoding="utf-8-sig") as file:
        pools_document = json.load(file)
    pools = pools_document.get("pools", {})
    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as file:
        catalog = json.load(file)
    lookup = load_catalog_lookup(CATALOG_PATH)

    changed, unmatched = apply_pools(catalog, lookup, pools, write=not args.check)

    if unmatched:
        print(f"[StandardPools] {len(unmatched)} pool names are not in the catalog:")
        for game_type, item_type, name in unmatched[:30]:
            print(f"  game {game_type} {item_type}: {name}")

    if args.check:
        if changed:
            print(f"[StandardPools] {len(changed)} catalog flags differ from standard_pools.json:")
            for game_type, item_type, name, expected in changed[:30]:
                print(f"  game {game_type} {item_type}: {name} -> {expected}")
            sys.exit(1)
        print("[StandardPools] Catalog matches standard_pools.json.")
        return

    with open(CATALOG_PATH, "w", encoding="utf-8") as file:
        json.dump(catalog, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"[StandardPools] Applied {len(changed)} changes to game_catalog.json.")


if __name__ == "__main__":
    main()
