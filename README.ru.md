# GachaPoint Data Hub

[🇬🇧 Read in English](README.md)

Официальный открытый репозиторий данных для приложения **GachaPoint**: актуальные промокоды, база персонажей и оружия, расписание и хроника баннеров для игр HoYoverse (Genshin Impact, Honkai: Star Rail, Zenless Zone Zero и Honkai Impact 3rd).

---

## 📁 Структура репозитория

| Файл | Описание | Локализация |
| :--- | :--- | :--- |
| `promocodes.json` | Каталог активных промокодов по 4 играм, сроки действия, статусы (`STREAM`, `NEW`, `PERMANENT`) и типы наград | Двуязычный (`rewards_description_ru`, `rewards_description_en`) |
| `game_catalog.json` | База персонажей и оружия, стандартный пул для умного определения 50/50 и прямые URL аватарок из CDN | Двуязычный (`name_ru`, `name_en`), иконки CDN |
| `banners_schedule.json` | Расписание текущих, будущих и прошедших баннеров с таймерами и привязкой к патчам | Двуязычный (`featured_five_stars_ru`, `featured_five_stars_en`) |
| `sync_promocodes.py` | Автоматический скрипт валидации и обновления | Автономный |
| `.github/workflows/sync.yml` | GitHub Actions workflow ежедневной проверки и обновления | CI/CD |

---

## 🛠️ Схемы данных

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

## 🚀 Как отправить обновления в GitHub

В терминале:
```bash
cd "e:\Programming\Android Projects\HoyoSubsTrakcer\data-automation"
git add .
git commit -m "feat: bilingual schema, 2026 banners, active codes, and media"
git push origin main
```

## ⚙️ Включение прав на запись для GitHub Actions
1. Откройте репозиторий: `https://github.com/MenshovAnton/GachaPoint-Data`
2. Перейдите в **Settings ➔ Actions ➔ General**.
3. В блоке **Workflow permissions** выберите **Read and write permissions**.
4. Нажмите кнопку **Save**.
