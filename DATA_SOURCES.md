# GachaPoint Data Hub — sources and verification policy

## Publication policy

- Published datasets contain only records confirmed by an official HoYoverse source.
- Fandom MediaWiki is used for discovery only. Scraped candidates are written to
  `quarantine_codes.json` and are not exposed to the Android client.
- Published `ACTIVE`, `STREAM`, and `NEW` promo codes must have
  `verification_status: verified`. Unverified codes are moved to
  `quarantine_codes.json` on every sync.
- Permanent promo codes are kept as `legacy`; they require a manual review if a
  code stops working.
- Official texts (in-game announcements, website news and official HoYoLAB
  posts) are scanned for candidate codes on every sync. A code is published
  automatically only when its exact value appears in an official text and the
  reward quantities can be extracted from the surrounding text.
- Codes that cannot be confirmed automatically stay in `quarantine_codes.json`
  and are sent to Telegram for manual review. The review result is applied with
  `scripts/tools/apply_code_checks.py` or the `Verify Promo Code` workflow.
- A code confirmed in-game may be published with
  `source_type: manual_in_game`, `verification_status: verified` and a
  `verified_at` timestamp.
- A `CURRENT` or `ANNOUNCED` banner without an official source is moved to
  `pending_banners.json` before the dataset is saved.
- Historical records without a source are kept as `verification_status: legacy`.
- The linter rejects `CURRENT`/`ANNOUNCED` banners without an official `source_url`,
  `verification_status: verified`, and `verified_at`.

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
| `source_url` | Official HoYoverse, HoYoLAB, or official social post URL |
| `source_id` | Announcement/news ID used for audit |
| `source_type` | `official`, `manual_in_game` or `community` |
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
