# GachaPoint Data Hub

[🇷🇺 Читать на русском](README.ru.md)

Official open data source for **GachaPoint**: active promo codes, character & weapon database, and banner schedule / chronicle for HoYoverse games (Genshin Impact, Honkai: Star Rail, Zenless Zone Zero, and Honkai Impact 3rd).

---

## 📁 Repository Structure

| File | Description | Localization |
| :--- | :--- | :--- |
| `promocodes.json` | Active promo codes for all 4 games, with expiry dates, status (`STREAM`, `ACTIVE`, `PERMANENT`, `EXPIRED`), and reward types | Bilingual (`rewards_description_ru`, `rewards_description_en`) |
| `game_catalog.json` | Characters and weapons catalog, 5★ standard pool identification for automatic 50/50 recognition, and CDN avatar image URLs | Bilingual (`name_ru`, `name_en`), aliases, icon CDN |
| `banners_schedule.json` | Official current, past, and upcoming banner schedules with countdown timestamps and patch mapping | Bilingual (`featured_five_stars_ru`, `featured_five_stars_en`) |
| `add_entity.py` | Autonomous CLI tool to fetch official avatar icons and register new entities | All 4 games |
| `sync_promocodes.py` | Autonomous scraping, status moderation & synchronization script | Independent |
| `lint_data.py` | Strict schema and cross-reference integrity linter | Independent |
| `.github/workflows/sync.yml` | GitHub Actions workflow running automated sync checks every 3 hours | CI/CD |

---

## 🤖 Automation & Maintenance

### 1. Automated GitHub Actions Sync
The repository automatically executes `.github/workflows/sync.yml` every 3 hours:
- Scrapes Fandom MediaWiki APIs for active livestream and promotional codes.
- Queries HoYoLAB News API for newly announced official event wishes and banners.
- Moderates calendar expiration dates (`CURRENT`, `UPCOMING`, `ENDED`).
- Runs `lint_data.py` to ensure zero errors and zero broken references.

### 2. Adding a New Character / Weapon
When a new character or signature weapon is announced or released, run:
```bash
python add_entity.py --game 0 --name-ru "Скирк" --name-en "Skirk" --rarity "5★" --type CHARACTER
```
The script automatically:
1. Queries Fandom MediaWiki for official square in-game icons/busts.
2. Normalizes the image into 256×256 (or 512×512) RGBA PNG in `avatars/<game>/`.
3. Registers the entity with canonical URLs and aliases in `game_catalog.json`.
4. Validates repository integrity via `lint_data.py`.

---

## ⚖️ Legal Disclaimer

*GachaPoint Data Hub* is an open-source, non-commercial fan-made project created for educational and utility purposes.

- This project is **not affiliated with, endorsed, sponsored, or approved by miHoYo / HoYoverse (COGNOSPHERE PTE. LTD.)**.
- *Genshin Impact*, *Honkai: Star Rail*, *Zenless Zone Zero*, *Honkai Impact 3rd*, and all associated character names, weapon names, imagery, and intellectual properties are registered trademarks and copyrights of **COGNOSPHERE PTE. LTD.** / **miHoYo**.
- All in-game assets and thumbnail crops stored in this repository are used under **Fair Use** guidelines for identification and cataloging purposes in a free community utility tool.
