[English](README.md) | [Русский](README.ru.md)

<h1 align="center">GachaPoint Data Hub</h1>

<p align="center">
  Автономный пайплайн верификации и открытая база данных для <b>GachaPoint</b><br>
  Поддерживает <b>Genshin Impact</b>, <b>Honkai: Star Rail</b>, <b>Zenless Zone Zero</b> и <b>Honkai Impact 3rd</b>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/пайплайн-автономный-brightgreen?style=flat-square" alt="Pipeline Status">
  <img src="https://img.shields.io/badge/валидация-строгий_линтер-blue?style=flat-square" alt="Validation">
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="CI">
  <a href="https://t.me/GachaPoint_official"><img src="https://img.shields.io/badge/Telegram-@GachaPoint__official-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="Telegram"></a>
</p>

---

## 📖 Обзор

**GachaPoint Data Hub** — это открытый центральный репозиторий данных для мобильного приложения [GachaPoint](https://github.com/MenshovAnton/GachaPoint). Он собирает, валидирует и предоставляет проверенные игровые данные:
- **Действующие промокоды и коды со стримов:** с автоматическим таймером истечения и переведенными наградами.
- **Каталог игровых сущностей:** полные списки персонажей, оружия, световых конусов, амплификаторов и помощников с разметкой стандартного пула 50/50 и ссылками на официальные квадратные иконки.
- **Расписание баннеров и хроника реранов:** полная хронология версий и актуальные молитвы/прыжки событий.

---

## 📁 Структура репозитория

| Файл | Назначение | Формат и локализация |
| :--- | :--- | :--- |
| [`promocodes.json`](promocodes.json) | Активные, стрим, постоянные и архивные промокоды | `rewards_description_ru`, `rewards_description_en`, `reward_types` |
| [`game_catalog.json`](game_catalog.json) | Каталог персонажей, оружия и спутников | `name_ru`, `name_en`, `rarity`, `type`, `icon_url`, `is_standard`, `aliases` |
| [`banners_schedule.json`](banners_schedule.json) | Прошедшие, текущие и анонсированные баннеры | `version`, `phase`, `start_date`, `end_date`, `featured_five_stars_ru/en` |
| [`lint_data.py`](lint_data.py) | Строгий валидатор целостности и схем | Сквозная проверка баннеров, аватарок и алиасов каталога |
| [`sync_promocodes.py`](sync_promocodes.py) | Автономная модерация, парсер Fandom MediaWiki и HoYoLAB | Запускается каждые 3 часа через GitHub Actions |

---

## 🎮 Редкости и типы сущностей по играм

Каждая игра использует аутентичную терминологию:

| Game Type | Игра | Высшая редкость | Эпическая редкость | Дополнительные типы |
| :---: | :--- | :---: | :---: | :--- |
| `0` | **Genshin Impact** | `5★` | `4★` | `CHARACTER`, `WEAPON` |
| `1` | **Honkai: Star Rail** | `5★` | `4★` | `CHARACTER`, `WEAPON` (Световые конусы) |
| `2` | **Zenless Zone Zero** | `S` (S-ранг) | `A` (A-ранг) | `CHARACTER`, `WEAPON` (Амплификаторы), `BANGBOO` |
| `3` | **Honkai Impact 3rd** | `S` (S-ранг) | `A` (A-ранг) | `CHARACTER` (Баттлсьюты), `WEAPON`, `ASTRAL_OP`, `ELF` |

---

## 🤖 Автоматизация

### 1. Расписание GitHub Actions (`.github/workflows/sync.yml`)
Выполняется каждые 3 часа:
- Скрейпит MediaWiki API Fandom на наличие новых кодов и трансляций.
- Модерирует статусы баннеров (`CURRENT`, `ANNOUNCED`, `EXPIRED`) по календарю.
- Запускает `lint_data.py` для предотвращения битых ссылок и некорректных схем перед коммитом.
- Отправляет уведомления в Telegram-канал при появлении новых кодов.

### 2. Добавление персонажа или оружия
Через CLI-утилиту `add_entity.py`:
```bash
python add_entity.py --game 0 --name-ru "Скирк" --name-en "Skirk" --rarity "5★" --type CHARACTER
```
Утилита находит официальную квадратную иконку, сохраняет в `avatars/<game>/` и регистрирует алиасы в `game_catalog.json`.

---

## ⚖️ Правовая информация (Fair Use)

*GachaPoint Data Hub* — некоммерческий фанатский проект с открытым исходным кодом.
- Проект **не связан с компанией miHoYo / HoYoverse (COGNOSPHERE PTE. LTD.)**, не спонсируется и не утверждается ею.
- Все торговые марки, названия персонажей и графические материалы принадлежат компании **COGNOSPHERE PTE. LTD.** / **miHoYo**.
- Все миниатюры и изображения в репозитории используются в справочных целях в бесплатном приложении на основе принципов **Fair Use** (добросовестного использования).
