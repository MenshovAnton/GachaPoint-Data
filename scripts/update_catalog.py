#!/usr/bin/env python3
"""
Comprehensive Catalog Expansion & Normalization Script
- Removes duplicates (e.g. Dan Heng IL in HSR)
- Injects comprehensive aliases for ZZZ, HI3, Genshin, HSR
- Adds missing 4★ and standard roster characters for all 4 games
- Normalizes naming across banners_schedule.json and game_catalog.json
"""

import json
import os
from typing import Dict, List, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "game_catalog.json")
BANNERS_PATH = os.path.join(BASE_DIR, "banners_schedule.json")

# New characters to inject into Game 0 (Genshin Impact)
GENSHIN_NEW_CHARACTERS = [
    {"name_ru": "Барбара", "name_en": "Barbara", "rarity": "4★", "is_standard": True, "icon": "barbara.png", "aliases": ["Барбара", "Barbara"]},
    {"name_ru": "Ноэлль", "name_en": "Noelle", "rarity": "4★", "is_standard": True, "icon": "noelle.png", "aliases": ["Ноэлль", "Noelle"]},
    {"name_ru": "Диона", "name_en": "Diona", "rarity": "4★", "is_standard": False, "icon": "diona.png", "aliases": ["Диона", "Diona"]},
    {"name_ru": "Бэй Доу", "name_en": "Beidou", "rarity": "4★", "is_standard": False, "icon": "beidou.png", "aliases": ["Бэй Доу", "Бэйдоу", "Beidou"]},
    {"name_ru": "Нин Гуан", "name_en": "Ningguang", "rarity": "4★", "is_standard": False, "icon": "ningguang.png", "aliases": ["Нин Гуан", "Нингуан", "Ningguang"]},
    {"name_ru": "Синь Янь", "name_en": "Xinyan", "rarity": "4★", "is_standard": False, "icon": "xinyan.png", "aliases": ["Синь Янь", "Синьянь", "Xinyan"]},
    {"name_ru": "Чун Юнь", "name_en": "Chongyun", "rarity": "4★", "is_standard": False, "icon": "chongyun.png", "aliases": ["Чун Юнь", "Чунъюнь", "Chongyun"]},
    {"name_ru": "Рэйзор", "name_en": "Razor", "rarity": "4★", "is_standard": False, "icon": "razor.png", "aliases": ["Рэйзор", "Рейзор", "Razor"]},
    {"name_ru": "Розария", "name_en": "Rosaria", "rarity": "4★", "is_standard": False, "icon": "rosaria.png", "aliases": ["Розария", "Rosaria"]},
    {"name_ru": "Янь Фэй", "name_en": "Yanfei", "rarity": "4★", "is_standard": False, "icon": "yanfei.png", "aliases": ["Янь Фэй", "Яньфэй", "Yanfei"]},
    {"name_ru": "Саю", "name_en": "Sayu", "rarity": "4★", "is_standard": False, "icon": "sayu.png", "aliases": ["Саю", "Sayu"]},
    {"name_ru": "Кудзё Сара", "name_en": "Kujou Sara", "rarity": "4★", "is_standard": False, "icon": "kujou_sara.png", "aliases": ["Кудзё Сара", "Сара", "Kujou Sara", "Sara"]},
    {"name_ru": "Тома", "name_en": "Thoma", "rarity": "4★", "is_standard": False, "icon": "thoma.png", "aliases": ["Тома", "Thoma"]},
    {"name_ru": "Горо", "name_en": "Gorou", "rarity": "4★", "is_standard": False, "icon": "gorou.png", "aliases": ["Горо", "Gorou"]},
    {"name_ru": "Юнь Цзинь", "name_en": "Yun Jin", "rarity": "4★", "is_standard": False, "icon": "yun_jin.png", "aliases": ["Юнь Цзинь", "Юньцзинь", "Yun Jin", "Yunjin"]},
    {"name_ru": "Сиканоин Хэйдзо", "name_en": "Shikanoin Heizou", "rarity": "4★", "is_standard": False, "icon": "shikanoin_heizou.png", "aliases": ["Сиканоин Хэйдзо", "Хэйдзо", "Shikanoin Heizou", "Heizou"]},
    {"name_ru": "Коллеи", "name_en": "Collei", "rarity": "4★", "is_standard": False, "icon": "collei.png", "aliases": ["Коллеи", "Collei"]},
    {"name_ru": "Дори", "name_en": "Dori", "rarity": "4★", "is_standard": False, "icon": "dori.png", "aliases": ["Дори", "Dori"]},
    {"name_ru": "Лайла", "name_en": "Layla", "rarity": "4★", "is_standard": False, "icon": "layla.png", "aliases": ["Лайла", "Layla"]},
    {"name_ru": "Фарузан", "name_en": "Faruzan", "rarity": "4★", "is_standard": False, "icon": "faruzan.png", "aliases": ["Фарузан", "Фаризан", "Faruzan"]},
    {"name_ru": "Яо Яо", "name_en": "Yaoyao", "rarity": "4★", "is_standard": False, "icon": "yaoyao.png", "aliases": ["Яо Яо", "Яояо", "Yaoyao"]},
    {"name_ru": "Кавех", "name_en": "Kaveh", "rarity": "4★", "is_standard": False, "icon": "kaveh.png", "aliases": ["Кавех", "Kaveh"]},
    {"name_ru": "Кирара", "name_en": "Kirara", "rarity": "4★", "is_standard": False, "icon": "kirara.png", "aliases": ["Кирара", "Kirara"]},
    {"name_ru": "Линетт", "name_en": "Lynette", "rarity": "4★", "is_standard": False, "icon": "lynette.png", "aliases": ["Линетт", "Линнетт", "Lynette"]},
    {"name_ru": "Фремине", "name_en": "Freminet", "rarity": "4★", "is_standard": False, "icon": "freminet.png", "aliases": ["Фремине", "Freminet"]},
    {"name_ru": "Шарлотта", "name_en": "Charlotte", "rarity": "4★", "is_standard": False, "icon": "charlotte.png", "aliases": ["Шарлотта", "Charlotte"]},
    {"name_ru": "Шеврёз", "name_en": "Chevreuse", "rarity": "4★", "is_standard": False, "icon": "chevreuse.png", "aliases": ["Шеврёз", "Шеврез", "Chevreuse"]},
    {"name_ru": "Ка Мин", "name_en": "Gaming", "rarity": "4★", "is_standard": False, "icon": "gaming.png", "aliases": ["Ка Мин", "Камин", "Gaming"]},
    {"name_ru": "Сетос", "name_en": "Sethos", "rarity": "4★", "is_standard": False, "icon": "sethos.png", "aliases": ["Сетос", "Сетхос", "Sethos"]},
    {"name_ru": "Эмбер", "name_en": "Amber", "rarity": "4★", "is_standard": True, "icon": "amber.png", "aliases": ["Эмбер", "Amber"]},
    {"name_ru": "Кэйа", "name_en": "Kaeya", "rarity": "4★", "is_standard": True, "icon": "kaeya.png", "aliases": ["Кэйа", "Кейа", "Kaeya"]},
    {"name_ru": "Лиза", "name_en": "Lisa", "rarity": "4★", "is_standard": True, "icon": "lisa.png", "aliases": ["Лиза", "Lisa"]},
    {"name_ru": "Элой", "name_en": "Aloy", "rarity": "5★", "is_standard": True, "icon": "aloy.png", "aliases": ["Элой", "Aloy"]},
    {"name_ru": "Иансан", "name_en": "Iansan", "rarity": "4★", "is_standard": False, "icon": "iansan.png", "aliases": ["Иансан", "Iansan"]},
    {"name_ru": "Ифа", "name_en": "Ifa", "rarity": "4★", "is_standard": False, "icon": "ifa.png", "aliases": ["Ифа", "Ifa"]},
    {"name_ru": "Айно", "name_en": "Aino", "rarity": "4★", "is_standard": False, "icon": "aino.png", "aliases": ["Айно", "Aino"]},
    {"name_ru": "Ягода", "name_en": "Jahoda", "rarity": "4★", "is_standard": False, "icon": "jahoda.png", "aliases": ["Ягода", "Jahoda"]},
    {"name_ru": "Иллуга", "name_en": "Illuga", "rarity": "4★", "is_standard": False, "icon": "illuga.png", "aliases": ["Иллуга", "Illuga"]},
    {"name_ru": "Алёша", "name_en": "Alyosha", "rarity": "4★", "is_standard": False, "icon": "alyosha.png", "aliases": ["Алёша", "Алеша", "Alyosha"]}
]

# New characters to inject into Game 1 (Honkai: Star Rail)
HSR_NEW_CHARACTERS = [
    {"name_ru": "Наташа", "name_en": "Natasha", "rarity": "4★", "is_standard": True, "icon": "natasha.png", "aliases": ["Наташа", "Natasha"]},
    {"name_ru": "Аста", "name_en": "Asta", "rarity": "4★", "is_standard": True, "icon": "asta.png", "aliases": ["Аста", "Asta"]},
    {"name_ru": "Сервал", "name_en": "Serval", "rarity": "4★", "is_standard": True, "icon": "serval.png", "aliases": ["Сервал", "Serval"]},
    {"name_ru": "Сампо", "name_en": "Sampo", "rarity": "4★", "is_standard": False, "icon": "sampo.png", "aliases": ["Сампо", "Sampo", "Sampo Koski"]},
    {"name_ru": "Хук", "name_en": "Hook", "rarity": "4★", "is_standard": False, "icon": "hook.png", "aliases": ["Хук", "Hook"]},
    {"name_ru": "Сушан", "name_en": "Sushang", "rarity": "4★", "is_standard": False, "icon": "sushang.png", "aliases": ["Сушан", "Sushang"]},
    {"name_ru": "Цинцюэ", "name_en": "Qingque", "rarity": "4★", "is_standard": False, "icon": "qingque.png", "aliases": ["Цинцюэ", "Цинцюе", "Qingque"]},
    {"name_ru": "Юйкун", "name_en": "Yukong", "rarity": "4★", "is_standard": False, "icon": "yukong.png", "aliases": ["Юйкун", "Yukong"]},
    {"name_ru": "Лука", "name_en": "Luka", "rarity": "4★", "is_standard": False, "icon": "luka.png", "aliases": ["Лука", "Luka"]},
    {"name_ru": "Рысь", "name_en": "Lynx", "rarity": "4★", "is_standard": False, "icon": "lynx.png", "aliases": ["Рысь", "Lynx", "Lynx Landau"]},
    {"name_ru": "Гуйнайфэнь", "name_en": "Guinaifen", "rarity": "4★", "is_standard": False, "icon": "guinaifen.png", "aliases": ["Гуйнайфэнь", "Гуйнайфен", "Guinaifen"]},
    {"name_ru": "Ханья", "name_en": "Hanya", "rarity": "4★", "is_standard": False, "icon": "hanya.png", "aliases": ["Ханья", "Hanya"]},
    {"name_ru": "Сюэи", "name_en": "Xueyi", "rarity": "4★", "is_standard": False, "icon": "xueyi.png", "aliases": ["Сюэи", "Xueyi"]},
    {"name_ru": "Миша", "name_en": "Misha", "rarity": "4★", "is_standard": False, "icon": "misha.png", "aliases": ["Миша", "Misha"]},
    {"name_ru": "Моцзэ", "name_en": "Moze", "rarity": "4★", "is_standard": False, "icon": "moze.png", "aliases": ["Моцзэ", "Модзе", "Moze"]},
    {"name_ru": "Арлан", "name_en": "Arlan", "rarity": "4★", "is_standard": False, "icon": "arlan.png", "aliases": ["Арлан", "Arlan"]}
]

# New battlesuits for Game 3 (Honkai Impact 3rd)
HI3_NEW_CHARACTERS = [
    {"name_ru": "Ночной оруженосец", "name_en": "Night Squire", "rarity": "4★", "is_standard": False, "icon": "night_squire.png", "aliases": ["Ночной оруженосец", "Night Squire"]},
    {"name_ru": "Валькирия Рейнджер", "name_en": "Valkyrie Ranger", "rarity": "4★", "is_standard": False, "icon": "valkyrie_ranger.png", "aliases": ["Валькирия Рейнджер", "Valkyrie Ranger"]},
    {"name_ru": "Грешная Сакитама", "name_en": "Flame Sakitama", "rarity": "4★", "is_standard": False, "icon": "flame_sakitama.png", "aliases": ["Грешная Сакитама", "Flame Sakitama"]},
    {"name_ru": "Валькирия Глория", "name_en": "Valkyrie Gloria", "rarity": "4★", "is_standard": False, "icon": "valkyrie_gloria.png", "aliases": ["Валькирия Глория", "Valkyrie Gloria"]},
    {"name_ru": "Полуночная Полынь", "name_en": "Midnight Absinthe", "rarity": "4★", "is_standard": False, "icon": "midnight_absinthe.png", "aliases": ["Полуночная Полынь", "Midnight Absinthe"]},
    {"name_ru": "Сладкая и Пряная", "name_en": "Sweet 'n' Spicy", "rarity": "4★", "is_standard": False, "icon": "sweet_n_spicy.png", "aliases": ["Сладкая и Пряная", "Sweet 'n' Spicy", "Carole"]},
    {"name_ru": "Спина Астера", "name_en": "Spina Astera", "rarity": "5★", "is_standard": False, "icon": "spina_astera.png", "aliases": ["Спина Астера", "Spina Astera", "Rita"]},
    {"name_ru": "Золотая Дива", "name_en": "Golden Diva", "rarity": "4★", "is_standard": False, "icon": "golden_diva.png", "aliases": ["Золотая Дива", "Golden Diva", "Eden"]},
    {"name_ru": "Ночная Роза", "name_en": "Umbrall Rose", "rarity": "4★", "is_standard": False, "icon": "umbrall_rose.png", "aliases": ["Ночная Роза", "Umbrall Rose"]},
    {"name_ru": "Гельвеция", "name_en": "Helvetia", "rarity": "5★", "is_standard": False, "icon": "helvetia.png", "aliases": ["Гельвеция", "Helvetia"]}
]

def update_game_catalog():
    print("Loading game_catalog.json...")
    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        catalog = json.load(f)

    for g in catalog.get("games", []):
        gt = g.get("game_type")
        items = g.setdefault("items", [])

        # 1. Update Game 0 (Genshin)
        if gt == 0:
            existing_names = {it.get("name_ru", "").lower() for it in items}
            # Add aliases to existing
            for it in items:
                n_ru = it.get("name_ru", "")
                aliases = it.setdefault("aliases", [])
                if n_ru == "Куки Синобу":
                    for a in ["Синобу", "Shinobu", "Kuki"]:
                        if a not in aliases: aliases.append(a)
                elif n_ru == "Цзы Бай":
                    for a in ["Zi Bai", "Zibai", "Zibai"]:
                        if a not in aliases: aliases.append(a)
                elif n_ru == "Николь Рейн":
                    for a in ["Nicole Reeyn", "Nicole", "Николь"]:
                        if a not in aliases: aliases.append(a)
                elif n_ru == "Лоэн":
                    for a in ["Lohen", "Loen"]:
                        if a not in aliases: aliases.append(a)

            # Insert missing
            for new_c in GENSHIN_NEW_CHARACTERS:
                if new_c["name_ru"].lower() not in existing_names:
                    items.append({
                        "name_ru": new_c["name_ru"],
                        "name_en": new_c["name_en"],
                        "aliases": new_c["aliases"],
                        "rarity": new_c["rarity"],
                        "type": "CHARACTER",
                        "is_standard": new_c["is_standard"],
                        "icon_path": f"avatars/0/{new_c['icon']}"
                    })
                    existing_names.add(new_c["name_ru"].lower())
                    print(f"Added Genshin character: {new_c['name_ru']} ({new_c['name_en']})")

        # 2. Update Game 1 (HSR)
        elif gt == 1:
            # Remove duplicate Dan Heng IL
            cleaned_items = []
            seen_dh_il = False
            for it in items:
                if it.get("name_ru") == "Пожиратель Луны":
                    if seen_dh_il:
                        print("Removed duplicate 'Пожиратель Луны' from HSR")
                        continue
                    seen_dh_il = True
                    it["aliases"] = ["Dan Heng IL", "Dan Heng Imbibitor Lunae", "Dan Heng - Imbibitor Lunae", "IL", "Пожиратель Луны"]
                cleaned_items.append(it)
            items = cleaned_items
            g["items"] = items

            existing_names = {it.get("name_ru", "").lower() for it in items}
            for new_c in HSR_NEW_CHARACTERS:
                if new_c["name_ru"].lower() not in existing_names:
                    items.append({
                        "name_ru": new_c["name_ru"],
                        "name_en": new_c["name_en"],
                        "aliases": new_c["aliases"],
                        "rarity": new_c["rarity"],
                        "type": "CHARACTER",
                        "is_standard": new_c["is_standard"],
                        "icon_path": f"avatars/1/{new_c['icon']}"
                    })
                    existing_names.add(new_c["name_ru"].lower())
                    print(f"Added HSR character: {new_c['name_ru']} ({new_c['name_en']})")

        # 3. Update Game 2 (ZZZ)
        elif gt == 2:
            alias_map = {
                "Эллен Джо": ["Эллен", "Ellen", "Ellen Joe"],
                "Цезарь Кинг": ["Цезарь", "Caesar", "Caesar King"],
                "Бернис Уайт": ["Бернис", "Burnice", "Burnice White"],
                "Хосими Мияби": ["Мияби", "Miyabi", "Hoshimi Miyabi"],
                "Энби": ["Анби", "Anby", "Anby Demara"],
                "Николь": ["Nicole", "Nicole Demara"],
                "Билли": ["Billy", "Billy Kid"],
                "Корин": ["Corin", "Corin Wickes"],
                "Люси": ["Lucy", "Luciana", "Luciana de Montefio"],
                "Пайпер": ["Piper", "Piper Wheel"],
                "Сет": ["Seth", "Seth Lowell"],
                "Антон Иванов": ["Антон", "Anton", "Anton Ivanov"],
                "Бен Биггер": ["Бен", "Ben", "Ben Bigger"]
            }
            for it in items:
                n_ru = it.get("name_ru", "")
                if n_ru in alias_map:
                    it["aliases"] = alias_map[n_ru]

        # 4. Update Game 3 (HI3)
        elif gt == 3:
            alias_map = {
                "Сенадина": ["Senadina", "Deepspace Anchor: First Light"],
                "Лантерн": ["Lantern", "Lone Destruction: Shadowchaser"],
                "Телема": ["Thelema", "Mad Pleasure: Shadowbringer"],
                "Сонквэ": ["Songque", "Сунцюэ", "Jovial Deception: Shadowdimmer"],
                "Серапеум": ["Serapeum", "Morning Dawn"],
                "Вита": ["Vita", "Vita (Lone Planetfarer)", "Lone Planetfarer"],
                "Киана: Судья Финала": ["Kiana (Finality)", "Herrscher of Finality", "Finality"],
                "Элизия: Мисс Розовая Эльф": ["Miss Pink Elf♪", "Miss Pink Elf", "Elysia"],
                "Валькирия Стрела": ["Helia", "Хелия", "Valkyrie Boltstorm", "Valkyrie Boltstorm (Helia)"],
                "Валькирия Взрыв": ["Coralie", "Корали", "Valkyrie Blastmetal", "Valkyrie Blastmetal (Coralie)"],
                "Грисео: Звездная импрессионистка": ["Звездная импрессионистка", "Starry Impression"]
            }
            for it in items:
                n_ru = it.get("name_ru", "")
                if n_ru in alias_map:
                    it["aliases"] = alias_map[n_ru]

            existing_names = {it.get("name_ru", "").lower() for it in items}
            for new_c in HI3_NEW_CHARACTERS:
                if new_c["name_ru"].lower() not in existing_names:
                    items.append({
                        "name_ru": new_c["name_ru"],
                        "name_en": new_c["name_en"],
                        "aliases": new_c["aliases"],
                        "rarity": new_c["rarity"],
                        "type": "CHARACTER",
                        "is_standard": new_c["is_standard"],
                        "icon_path": f"avatars/3/{new_c['icon']}"
                    })
                    existing_names.add(new_c["name_ru"].lower())
                    print(f"Added HI3 battlesuit: {new_c['name_ru']} ({new_c['name_en']})")

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Successfully updated game_catalog.json")

def fix_banner_schedule_typos():
    print("Normalizing banner names in banners_schedule.json...")
    with open(BANNERS_PATH, "r", encoding="utf-8-sig") as f:
        bdata = json.load(f)

    # Replacement dictionary for known typos
    TYPO_REPLACEMENTS = {
        "Фаризан": "Фарузан",
        "Линнетт": "Линетт",
        "Сетхос": "Сетос",
        "Камин": "Ка Мин",
        "Анби": "Энби",
        "Модзе": "Моцзэ"
    }

    modified_count = 0
    for g in bdata.get("games", []):
        for b in g.get("banners", []):
            for field in ["featured_five_stars_ru", "featured_four_stars_ru"]:
                if field in b and isinstance(b[field], list):
                    new_list = []
                    for name in b[field]:
                        if name in TYPO_REPLACEMENTS:
                            new_name = TYPO_REPLACEMENTS[name]
                            new_list.append(new_name)
                            modified_count += 1
                        else:
                            new_list.append(name)
                    b[field] = new_list

    with open(BANNERS_PATH, "w", encoding="utf-8") as f:
        json.dump(bdata, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Fixed {modified_count} banner typos in banners_schedule.json")

if __name__ == "__main__":
    update_game_catalog()
    fix_banner_schedule_typos()
