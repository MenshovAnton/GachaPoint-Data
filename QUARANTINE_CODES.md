# Quarantine promo codes

These codes are not published until an official source or an in-game check
confirms them. The list below is kept in sync with `quarantine_codes.json`; if
the two disagree, the JSON file is the source of truth.

## Automatic checks

Every sync tries to confirm quarantined codes against official HoYoverse and
HoYoLAB texts. A code is published automatically when the exact code is found
in an official text and the reward quantities can be extracted. Other codes are
sent to Telegram for manual review.

## Manual review

Open the code in the game and set the result in `code_checks.json`:

- `ok` — the code was redeemed successfully;
- `expired` — the game says the code has expired;
- `invalid` — the code is invalid or not recognized.

Then apply the checks:

```bash
python -m scripts.tools.apply_code_checks
python -m scripts.tools.apply_code_checks --list-pending
python -m scripts.tools.apply_code_checks --set 3 LBWY2YI5V4 ok
python -m scripts.sync.sync_promocodes --no-scrape --no-verify
```

The `Verify Promo Code` workflow performs the same steps from GitHub Actions.

## Current quarantine

| Game | Code | Rewards | Community date | Reason |
| :--- | :--- | :--- | :---: | :--- |
| Honkai Impact 3rd | `LBWY2YI5V4` | 30 Crystals | 2026-10-22 | No official source found |

## After checking

A confirmed code is published with:

- `verification_status: verified`;
- `source_type: manual_in_game` or `source_type: official`;
- `verified_at`;
- exact `expires_at` if known, otherwise `null` and
  `expiry_confidence: unknown`.
