# GachaPoint Data Hub

[🇷🇺 Читать на русском](README.ru.md)

Official open data source for **GachaPoint**: active promo codes, character & weapon database, and banner schedule / chronicle for HoYoverse games (Genshin Impact, Honkai: Star Rail, Zenless Zone Zero, and Honkai Impact 3rd).

---

## 📁 Repository Structure

| File | Description | Localization |
| :--- | :--- | :--- |
| `promocodes.json` | Active promo codes for all 4 games, with expiry dates, status (`STREAM`, `NEW`, `PERMANENT`), and reward types | Bilingual (`rewards_description_ru`, `rewards_description_en`) |
| `game_catalog.json` | Characters and weapons catalog, 5★ standard pool identification for automatic 50/50 recognition, and CDN avatar image URLs | Bilingual (`name_ru`, `name_en`), icon CDN |
| `banners_schedule.json` | Official current, past, and upcoming banner schedules with countdown timestamps and patch mapping | Bilingual (`featured_five_stars_ru`, `featured_five_stars_en`) |
| `sync_promocodes.py` | Python automated verification & syncing script | Independent |
| `.github/workflows/sync.yml` | GitHub Actions workflow running automated sync checks daily & on push | CI/CD |

---

## 🛠️ Data Schemas

### 1. `promocodes.json`
```json
{
  "id": "genshin_epic2026",
  "game_type": 0,
  "code": "EPIC2026",
  "rewards_description_ru": "40 Камней Истока, 20 000 Моры, 3 Опыта героя",
  "rewards_description_en": "40 Primogems, 20,000 Mora, 3 Hero's Wit",
  "reward_types": ["PRIMOGEM", "MORA", "EXP"],
  "status": "NEW",
  "expires_at": "2026-11-15T00:00:00Z",
  "is_stream": false,
  "is_active": true
}
```

### 2. `game_catalog.json`
```json
{
  "name": "Скирк",
  "name_ru": "Скирк",
  "name_en": "Skirk",
  "rarity": "5★",
  "type": "CHARACTER",
  "is_standard": false,
  "icon_url": "https://enka.network/ui/UI_AvatarIcon_Skirk.png"
}
```

### 3. `banners_schedule.json`
```json
{
  "id": "genshin_7_1_2",
  "version": "7.1",
  "phase": 2,
  "start_date": "2026-10-14",
  "end_date": "2026-11-03",
  "status": "CURRENT",
  "featured_five_stars_ru": ["Скирк", "Эскофье"],
  "featured_five_stars_en": ["Skirk", "Escoffier"],
  "featured_four_stars_ru": ["Мика", "Кандакия", "Далия"],
  "featured_four_stars_en": ["Mika", "Candace", "Dahlia"]
}
```

---

## 🚀 How to Sync / Push to GitHub

In your terminal:
```bash
cd "e:\Programming\Android Projects\HoyoSubsTrakcer\data-automation"
git add .
git commit -m "feat: bilingual schema, 2026 banners, active codes, and media"
git push origin main
```

## ⚙️ Enabling Auto-Commit Permissions for GitHub Actions
1. Navigate to your repository: `https://github.com/MenshovAnton/GachaPoint-Data`
2. Open **Settings ➔ Actions ➔ General**.
3. Under **Workflow permissions**, choose **Read and write permissions**.
4. Click **Save**.
