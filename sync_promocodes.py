import json
import os
import re
import urllib.request
from datetime import datetime, timezone

CODE_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,30}$")

def validate_code(code: str) -> bool:
    if not code:
        return False
    return bool(CODE_REGEX.match(code.strip()))

def load_json(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "last_updated": datetime.now(timezone.utc).isoformat(), "codes": []}

def save_json(filepath: str, data: dict):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_community_codes(url: str):
    """Безопасный запрос к открытым источникам"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GachaPoint-DataBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Fetch failed for {url}: {e}")
    return None

def main():
    filepath = "promocodes.json"
    data = load_json(filepath)
    print(f"Loaded {len(data.get('codes', []))} existing promocodes.")

    existing_codes = {}
    for item in data.get("codes", []):
        raw_code = item.get("code", "").strip().upper()
        if validate_code(raw_code):
            key = (item.get("game_type"), raw_code)
            item["code"] = raw_code
            existing_codes[key] = item

    # Валидация и сохранение
    final_list = list(existing_codes.values())
    # Сортировка: сначала активные и стримовые
    final_list.sort(key=lambda x: (not x.get("is_active", True), not x.get("is_stream", False), x.get("game_type", 0)))

    data["codes"] = final_list
    save_json(filepath, data)
    print(f"Successfully validated and saved {len(final_list)} promocodes.")

if __name__ == "__main__":
    main()
