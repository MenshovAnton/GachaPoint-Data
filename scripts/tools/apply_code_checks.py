#!/usr/bin/env python3
"""
Apply manual in-game promo-code checks.

Reads code_checks.json, moves confirmed codes to promocodes.json and updates
the quarantine file. Use --dry-run to preview without writing.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKS_PATH = os.path.join(BASE_DIR, "code_checks.json")
PROMOCODES_PATH = os.path.join(BASE_DIR, "promocodes.json")
QUARANTINE_PATH = os.path.join(BASE_DIR, "quarantine_codes.json")

VALID_RESULTS = {"ok", "expired", "invalid"}
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def save_json(path, payload):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(tmp_path, path)


def apply_checks(checks, promocodes, quarantine, now):
    published = {
        (code.get("game_type", 0), code.get("code", "")): code
        for code in promocodes.get("codes", [])
    }
    quarantined = {
        (code.get("game_type", 0), code.get("code", "")): code
        for code in quarantine.get("codes", [])
    }

    applied = {"ok": 0, "expired": 0, "invalid": 0, "skipped": 0}

    for entry in checks.get("results", []):
        code_key = (int(entry.get("game_type", 0)), str(entry.get("code", "")).strip().upper())
        result = (entry.get("result") or "").strip().lower()
        if not result:
            continue
        if result not in VALID_RESULTS:
            print(f"Skipping {code_key[1]}: invalid result '{result}'")
            applied["skipped"] += 1
            continue

        item = quarantined.pop(code_key, None)
        if item is None:
            item = published.get(code_key)
        if item is None:
            print(f"Skipping {code_key[1]}: not found in quarantine or published data")
            applied["skipped"] += 1
            continue

        if result == "invalid":
            item["quarantine_reason"] = "checked_invalid"
            item["last_checked_at"] = now
            item["checked_note"] = entry.get("note", "")
            quarantined[code_key] = item
            applied["invalid"] += 1
            print(f"Marked invalid: {code_key[1]}")
            continue

        expires_at = entry.get("expires_at") or None
        item["status"] = "ACTIVE" if result == "ok" else "EXPIRED"
        item["is_active"] = result == "ok"
        item["expires_at"] = expires_at
        item["expiry_confidence"] = "official" if expires_at else "unknown"
        item["verification_status"] = "verified"
        item["verified_at"] = now
        item["source_type"] = "manual_in_game"
        item["checked_note"] = entry.get("note", "")
        item.pop("quarantine_reason", None)
        item.pop("last_checked_at", None)
        item.pop("last_notified_at", None)
        published[code_key] = item
        applied[result] += 1
        print(f"Applied {result}: {code_key[1]}")

    checks["checked_at"] = now
    promocodes["codes"] = list(published.values())
    quarantine["codes"] = list(quarantined.values())
    return applied


def find_or_create_check(checks, game_type, code):
    for entry in checks.setdefault("results", []):
        if int(entry.get("game_type", 0)) == game_type and str(entry.get("code", "")).strip().upper() == code:
            return entry
    entry = {"game_type": game_type, "code": code, "result": None, "expires_at": None, "note": ""}
    checks["results"].append(entry)
    return entry


def list_pending(checks, quarantine):
    pending = []
    for entry in checks.get("results", []):
        if not (entry.get("result") or "").strip():
            pending.append(entry)
    for entry in quarantine.get("codes", []):
        pending.append(entry)

    if not pending:
        print("No pending codes.")
        return

    seen = set()
    for entry in pending:
        game_type = int(entry.get("game_type", 0))
        code = str(entry.get("code", ""))
        key = (game_type, code)
        if key in seen:
            continue
        seen.add(key)
        rewards = entry.get("rewards_description_ru") or entry.get("rewards_ru") or ""
        print(f"{game_type} {code} | {rewards} | {entry.get('quarantine_reason', '')}")


def main():
    parser = argparse.ArgumentParser(description="Apply manual promo-code checks")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    parser.add_argument("--set", nargs=3, metavar=("GAME_TYPE", "CODE", "RESULT"),
                        help="Set a single result: --set 0 ABC123 ok")
    parser.add_argument("--expires-at", default=None, help="Exact expiry for --set")
    parser.add_argument("--note", default="", help="Optional note for --set")
    parser.add_argument("--list-pending", action="store_true", help="List codes awaiting verification")
    args = parser.parse_args()

    checks = load_json(CHECKS_PATH)
    promocodes = load_json(PROMOCODES_PATH)
    quarantine = load_json(QUARANTINE_PATH)

    if args.list_pending:
        list_pending(checks, quarantine)
        return

    if args.set:
        game_type = int(args.set[0])
        code = args.set[1].strip().upper()
        result = args.set[2].strip().lower()
        if game_type not in (0, 1, 2, 3):
            print(f"Invalid game type '{game_type}'. Use 0, 1, 2 or 3.")
            sys.exit(1)
        if not CODE_RE.match(code):
            print(f"Invalid code '{code}'.")
            sys.exit(1)
        if result not in VALID_RESULTS:
            print(f"Invalid result '{result}'. Use one of: {', '.join(sorted(VALID_RESULTS))}")
            sys.exit(1)
        entry = find_or_create_check(checks, game_type, code)
        entry["result"] = result
        entry["expires_at"] = args.expires_at
        entry["note"] = args.note

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    applied = apply_checks(checks, promocodes, quarantine, now)

    print(
        f"Summary: ok={applied['ok']}, expired={applied['expired']}, "
        f"invalid={applied['invalid']}, skipped={applied['skipped']}"
    )

    if args.dry_run:
        print("Dry run: files were not modified.")
        return

    save_json(PROMOCODES_PATH, promocodes)
    save_json(QUARANTINE_PATH, quarantine)
    save_json(CHECKS_PATH, checks)
    print("Updated promocodes.json, quarantine_codes.json and code_checks.json.")


if __name__ == "__main__":
    main()
