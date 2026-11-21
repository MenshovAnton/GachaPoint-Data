# GachaPoint Data Hub — sources and verification policy

## Publication policy

- Published datasets contain verified records confirmed by an official HoYoverse source, recognized trusted API, or verified in-game check.
- Data sources are structured into four tiers:
  - `official`: direct in-game announcements, official news feeds, official social channels (@GenshinImpact, @honkaistarrail, @ZZZ_KO).
  - `trusted_api`: high-reliability community API providers (e.g. Ennead API) whose entities resolve against `game_catalog.json`.
  - `manual_in_game`: confirmed through manual in-game check recorded in `code_checks.json`.
  - `community`: Fandom MediaWiki, Reddit, and social forums used for initial discovery only. Unverified candidates are kept in `quarantine_codes.json` / `pending_banners.json`.
- Published `ACTIVE`, `STREAM`, and `NEW` promo codes must have `verification_status: verified`. Unverified codes are moved to `quarantine_codes.json` on every sync.
- Permanent promo codes are kept as `legacy`; they require a manual review if a code stops working.
- Official texts and news feeds are scanned for candidate codes on every sync. A code is published automatically when its exact value appears in an official text and reward quantities can be extracted.
- Codes and banners that cannot be confirmed automatically stay in quarantine (`quarantine_codes.json`, `pending_banners.json`) and trigger Telegram review notifications.
- `CURRENT` and `ANNOUNCED` banners require `verification_status: verified`, valid dates matching calendar status, and all featured entities present in `game_catalog.json`.
- Historical records without a source are kept as `verification_status: legacy`.

## Official sources

### Genshin Impact

- In-game announcements (Event Wish posts):
  - `https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api/getAnnList`
  - `https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api/getAnnContent`
- Website news detail:
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/a1b1f9d3315447cc/getContent`
- Human-readable site: `https://genshin.hoyoverse.com/en/news`

### Honkai: Star Rail

- Website news API:
  - app id: `113fe6d3b4514cdd`
  - version-update channel: `250`
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/113fe6d3b4514cdd/getContentList`
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/113fe6d3b4514cdd/getContent`
- Event Warp posts (official HoYoLAB):
  - `https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList?gids=6&type=1&page_size=50&client_type=4`
  - `https://bbs-api-os.hoyolab.com/community/post/wapi/getPostFull?post_id=<id>`
- In-game announcement API:
  - `https://sg-hkrpg-api.hoyoverse.com/common/hkrpg_global/announcement/api/getAnnList`
- Human-readable site: `https://hsr.hoyoverse.com/en-us/news`

### Zenless Zone Zero

- Website news API:
  - app id: `3e9196a4b9274bd7`
  - limited-time channels: `288`
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/3e9196a4b9274bd7/getContentList`
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/3e9196a4b9274bd7/getContent`
- Human-readable site: `https://zenless.hoyoverse.com/en-us/news`

### Honkai Impact 3rd

- Website news API:
  - app id: `5fcd2aa439ca4aea`
  - update-announcement channel: `514`
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/5fcd2aa439ca4aea/getContentList`
  - `https://sg-public-api-static.hoyoverse.com/content_v2_user/app/5fcd2aa439ca4aea/getContent`
- Human-readable site: `https://honkaiimpact3.hoyoverse.com/global/en/news`

## Record metadata

Published records may contain these optional fields:

| Field | Meaning |
| :--- | :--- |
| `source_url` | Official HoYoverse, HoYoLAB, official social post, or trusted API URL |
| `source_id` | Announcement/news ID used for audit |
| `source_type` | `official`, `trusted_api`, `manual_in_game` or `community` |
| `last_checked_at` | Last automatic verification attempt |
| `last_notified_at` | Last Telegram review notification for quarantined codes |
| `verification_status` | `verified`, `legacy`, or `unverified` |
| `verified_at` | UTC timestamp of the verification run |
| `expiry_confidence` | `official`, `estimated`, or `unknown` |

## Standard-pool scope

Expected standard pools are stored in `standard_pools.json`:

- Genshin: Wanderlust Invocation;
- HSR: Stellar Warp;
- ZZZ: Star-Studded Cast and An Outstanding Partner;
- HI3: Dorm Supply.

The pools are machine-readable references maintained from the corresponding
community pool pages. `scripts/tools/apply_standard_pools.py --check` prevents
the catalog from drifting away from them. After a major game update, verify the
pool in-game and update `standard_pools.json` in the same commit.

## Manual verification

1. Open the official source URL.
2. Confirm the version, phase, dates, featured characters, and reward quantities.
3. Set `verification_status: verified` and `verified_at`.
4. Run `python -m scripts.tools.lint_data --strict` and `python -m unittest discover -s tests`.
5. Do not publish a banner or code if the official source does not confirm it.
