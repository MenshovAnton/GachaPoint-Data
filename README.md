[English](README.md) | [Русский](README.ru.md)

<h1 align="center">GachaPoint Data Hub</h1>

<p align="center">
  Autonomous high-integrity data pipeline and open datasets for <b>GachaPoint</b><br>
  Covering <b>Genshin Impact</b>, <b>Honkai: Star Rail</b>, <b>Zenless Zone Zero</b>, and <b>Honkai Impact 3rd</b>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/pipeline-automated-brightgreen?style=flat-square" alt="Pipeline Status">
  <img src="https://img.shields.io/badge/validation-strict_linter-blue?style=flat-square" alt="Validation">
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="CI">
  <a href="https://t.me/GachaPoint_official"><img src="https://img.shields.io/badge/Telegram-@GachaPoint__official-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="Telegram"></a>
</p>

---

## Overview

**GachaPoint Data Hub** is the central, open repository that powers the live data services in the [GachaPoint](https://github.com/MenshovAnton/GachaPoint) mobile app. It aggregates, validates, and serves verified game data:
- **Active & Livestream Promo Codes:** with automatic expiration countdowns and localized rewards.
- **Game Entities Catalog:** complete rosters of characters, weapons, light cones, W-Engines, and companions with standard 50/50 pool classification and square official avatar CDN URLs.
- **Banner Schedules & Rerun Chronicle:** chronological patch archives and current/upcoming event wishes.

---

## Repository Structure & Data Schemas

| File | Purpose | Localization & Structure |
| :--- | :--- | :--- |
| [`promocodes.json`](promocodes.json) | Active, stream, permanent, and recent archive promo codes | `rewards_description_ru`, `rewards_description_en`, `reward_types` |
| [`game_catalog.json`](game_catalog.json) | Characters, weapons, and companion catalog | `name_ru`, `name_en`, `rarity`, `type`, `icon_url`, `is_standard`, `aliases` |
| [`banners_schedule.json`](banners_schedule.json) | Past, current, and announced banner schedules | `version`, `phase`, `start_date`, `end_date`, `featured_five_stars_ru/en` |
| [`lint_data.py`](lint_data.py) | Zero-tolerance integrity & schema validator | Cross-references banners, avatars, and catalog aliases |
| [`sync_promocodes.py`](sync_promocodes.py) | Autonomous moderation, Fandom scraper & HoYoLAB parser | Runs every 3 hours via GitHub Actions |

---

## Game Ranks & Entity Types

Each game uses native, authentic terminology:

| Game Type | Game | Primary Rarity | Secondary Rarity | Companion / Special Entity Type |
| :---: | :--- | :---: | :---: | :--- |
| `0` | **Genshin Impact** | `5★` | `4★` | `CHARACTER`, `WEAPON` |
| `1` | **Honkai: Star Rail** | `5★` | `4★` | `CHARACTER`, `WEAPON` (Light Cones) |
| `2` | **Zenless Zone Zero** | `S` (S-Rank) | `A` (A-Rank) | `CHARACTER`, `WEAPON` (W-Engines), `BANGBOO` |
| `3` | **Honkai Impact 3rd** | `S` (S-Rank) | `A` (A-Rank) | `CHARACTER` (Battlesuits), `WEAPON`, `ASTRAL_OP`, `ELF` |

---

## Automation Pipeline

### 1. Scheduled GitHub Actions Sync (`.github/workflows/sync.yml`)
Runs every 3 hours:
- Scrapes Fandom MediaWiki APIs for active livestream codes and promo drops.
- Performs calendar moderation (`CURRENT`, `ANNOUNCED`, `EXPIRED`) for banner phases.
- Runs `lint_data.py` to guarantee zero broken references and schema compliance before commits.
- Dispatches Telegram notifications to community channels on new code discoveries.

### 2. Adding New Characters or Weapons
Run `add_entity.py` CLI:
```bash
python add_entity.py --game 0 --name-ru "Скирк" --name-en "Skirk" --rarity "5★" --type CHARACTER
```
The tool queries official API endpoints, fetches the official in-game square icon, and registers aliases in `game_catalog.json`.

---

## Legal & Fair Use Disclaimer

*GachaPoint Data Hub* is an open-source, non-commercial fan-made repository created for informational and utility purposes.
- This project is **not affiliated with, endorsed, sponsored, or approved by miHoYo / HoYoverse (COGNOSPHERE PTE. LTD.)**.
- *Genshin Impact*, *Honkai: Star Rail*, *Zenless Zone Zero*, *Honkai Impact 3rd*, and all related character names, assets, and trademarks belong to **COGNOSPHERE PTE. LTD.** / **miHoYo**.
- All game thumbnails and icon crops stored in this repository are used strictly under **Fair Use** for identification in a free utility tool.
