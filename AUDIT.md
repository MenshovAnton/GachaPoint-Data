[English](AUDIT.md) | [Русский](AUDIT.ru.md)

# GachaPoint Data Hub — audit report

Date: 2026-11-09.

## Summary

The scheduled `Sync Promocodes and Schedule` workflow had been failing since
2026-11-08. The published `main` branch still contained data produced by an
older parser: unverified active codes with synthetic expiry dates and
`CURRENT`/`ANNOUNCED` banners without official sources.

The audit reproduced the failure, replaced the unsafe merge path with a
quarantine-first flow, added official-source verification, and hardened the
linter so the same data cannot be published again.

## Pipeline status before the fix

- Last successful scheduled run: `42443584936` (2026-11-08 03:38 UTC).
- Failing runs: `42576011096`, `42529451723`, `42498185720`.
- Failure step: `Run lint and integrity validation` after sync.
- Root cause: the old sync re-published `KEEPUPWITHMITYA` with the bare reward
  `Камни Истока`, and the strict linter rejected it. The commit step was
  skipped, so every run lost its updates.

## Data problems found

- 28 `ACTIVE` codes in `main` had no `verification_status` and used synthetic
  expiry dates (`2026-11-26T06:32:4x`, `2026-12-09T12:00:00Z`).
- HSR `hsr_4_6_2`, `hsr_4_7_1`, `hsr_4_7_2`, ZZZ `zzz_3_3_1`, `zzz_3_3_2` and
  HI3 `hi3_9_1_1` were `CURRENT`/`ANNOUNCED` without `source_url`,
  `verification_status` or `verified_at`.
- `JRNY2SKY` had a corrupted Russian rewards description
  (`300 ??????????, 30 000 ?????...`).
- `YUANSHEN` was `EXPIRED` but had a future `expires_at`.
- 19 HI3 legacy codes used synthetic `2023-01-01` / `2023-01-31` dates.
- `ZZZTVCM` was treated as permanent; `CODE_VERIFICATION.md` and
  `QUARANTINE_CODES.md` disagreed with the JSON datasets.

## What changed

- `scripts/parsers/official_codes_parser.py` scans official Genshin
  announcements, HSR/ZZZ/HI3 website news and HoYoLAB news for candidate codes.
  It publishes a code automatically only when the exact code is present and the
  reward quantities can be extracted.
- `scripts/sync/sync_promocodes.py` now quarantines unverified active codes
  before publishing, verifies them against official texts, sends ambiguous
  cases to Telegram, and refuses to write an empty or drastically smaller
  `banners_schedule.json`.
- `scripts/tools/apply_code_checks.py` supports `--set` and `--list-pending` so
  a Telegram review result can be applied in one command.
- `scripts/tools/lint_data.py` rejects broken characters, future expiry on
  expired records, unverified active codes, unexpected permanent codes,
  non-detail source URLs and quarantine/published duplicates.
- `.github/workflows/sync.yml` validates the committed datasets, standard pools
  and parser tests before syncing.
- `.github/workflows/verify-code.yml` applies a single manual verification and
  pushes the result.

## Cross-repository note

The Android client now ignores a remote dataset whose `updated_at` is older
than the cached copy. This prevents a stale `main` branch from downgrading the
fixed assets shipped with the app.

## Verification policy

1. Official text match with rewards → publish automatically.
2. Official text match without rewards, or no match → keep in
   `quarantine_codes.json` and send a Telegram digest.
3. In-game confirmation → `source_type: manual_in_game`,
   `verification_status: verified`, `verified_at`.
4. Fandom is discovery only; it never publishes a code by itself.

## Limitation

Many HoYoverse codes are published only inside images (livestream infographics,
X posts). The pipeline does not perform OCR, so such codes cannot be confirmed
from text and always require the Telegram review step. Text-bearing official
posts are verified automatically.

## Local commands

```bash
python -m unittest discover -s tests
python -m scripts.tools.lint_data --strict
python -m scripts.tools.apply_standard_pools --check
python -m scripts.sync.sync_promocodes --no-scrape
python -m scripts.tools.apply_code_checks --list-pending
```

## Acceptance criteria

- Parser tests and the strict linter pass on local, remote and post-sync data.
- Three consecutive `workflow_dispatch` runs and one scheduled run are green.
- Every `ACTIVE` code has an official source or a manual in-game check.
- Every `CURRENT`/`ANNOUNCED` banner has an official detail `source_url`,
  `source_id`, `verification_status: verified` and `verified_at`.
- No synthetic dates and no broken characters in published datasets.
