# Promo-code verification

## Policy

Only codes confirmed by an official HoYoverse/HoYoLAB/official social source or
by an in-game check are published as `ACTIVE` or `STREAM`. Fandom MediaWiki is
used for discovery only. Unverified candidates are written to
`quarantine_codes.json` and are not exposed to the Android client.

## Automatic verification

Every sync scans recent official texts:

- Genshin Impact in-game announcements (`getAnnList` / `getAnnContent`);
- Honkai: Star Rail, Zenless Zone Zero and Honkai Impact 3rd website news
  (`getContentList` / `getContent`);
- official HoYoLAB news posts for all four games.

A code is published automatically only when the exact code appears in an
official text and the reward quantities can be extracted from the surrounding
text. Codes that are found without rewards, or are not found at all, stay
quarantined and are sent to Telegram for review.

## Manual in-game checks

`code_checks.json` stores the results of manual checks:

- `ok` — the code was redeemed successfully;
- `expired` — the game says the code has expired;
- `invalid` — the code is invalid or not recognized.

Apply checks with:

```bash
python -m scripts.tools.apply_code_checks
python -m scripts.tools.apply_code_checks --list-pending
python -m scripts.tools.apply_code_checks --set 0 ABC123 ok
```

The same result can be applied from GitHub Actions with the
`Verify Promo Code` workflow. Applied codes are marked
`verification_status: verified` and `source_type: manual_in_game`.

## Verified in the current dataset

Genshin Impact:

- `CDOF4X83H7X2`, `MIJIQ23V2437`, `PJ2KEBRAYSRM`, `PNKZ3WLNN8G6` — verified in
  game;
- `KEEPUPWITHMITYA` — official event page
  `https://genshin.hoyoverse.com/ru/news/detail/167189`.

Zenless Zone Zero:

- `HOLLOWRUN33`, `INKSHIFT33`, `LEVELUP33` — verified in game;
- `JRNY2SKY` — official 3.3 Special Program report
  `https://zenless.hoyoverse.com/en-us/news/detail/166644`.

Honkai Impact 3rd:

- `QPAS261QC8`, `SPECIALTREATS`, `KS58QWGR8W`, `NCU83WRBF2` — official
  `@HonkaiImpact3rd` X posts;
- `FLAVOR1`, `FLAVOR2`, `FLAVOR3`, `FLAVOR4` — official `@HonkaiImpact3rd`
  X post.

Honkai: Star Rail has no active limited-time codes in the current dataset.

## Permanent codes

The permanent allowlist is:

- `GENSHINGIFT` (Genshin Impact);
- `STARRAILGIFT`, `CREATIONNYMPH`, `FAREWELL`, `IFYOUAREREADINGTHIS`, `OMEGA`
  (Honkai: Star Rail);
- `ZENLESSGIFT` (Zenless Zone Zero);
- `HONKAIGIFT` (Honkai Impact 3rd).

## Still quarantined

See `quarantine_codes.json` and `QUARANTINE_CODES.md`. A quarantined code is
published only after an official source or an in-game check confirms it.
