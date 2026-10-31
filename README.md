# GachaPoint Data Hub

Официальный репозиторий данных для приложения **GachaPoint**: промокоды, база персонажей и расписание баннеров.

## Структура:
* `promocodes.json` — актуальные промокоды по 4 играм (Genshin, HSR, ZZZ, HI3).
* `game_catalog.json` — персонажи и оружие, стандартный пул для расчета 50/50.
* `banners_schedule.json` — расписание баннеров и патчей.
* `sync_promocodes.py` — робот валидации и обновления.
* `.github/workflows/sync.yml` — расписание GitHub Actions.

---

## Как залить в свой репозиторий (1 команда):

В терминале перейдите в папку `data-automation`:
```bash
cd "e:\Programming\Android Projects\HoyoSubsTrakcer\data-automation"
git init
git add .
git commit -m "feat: initial GachaPoint data hub"
git branch -M main
git remote add origin https://github.com/MenshovAnton/GachaPoint-Data.git
git push -u origin main --force
```

## Включение прав на автокоммит в GitHub:
В вашем репозитории на GitHub:
**Settings ➔ Actions ➔ General ➔ Workflow permissions ➔ установите флаг «Read and write permissions» ➔ Save**.
