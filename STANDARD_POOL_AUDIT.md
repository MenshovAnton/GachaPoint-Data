# Standard-pool audit

`is_standard` means "this item is obtainable from the permanent/standard banner,
channel, or supply". It is used by the Android client for 50/50 detection and
standard-banner suggestions.

The expected pools are stored in `standard_pools.json` and applied with:

```bash
python -m scripts.tools.apply_standard_pools
python -m scripts.tools.apply_standard_pools --check
```

## Current pools

| Game | Pool | Records |
| :--- | :--- | :--- |
| Genshin Impact | Wanderlust Invocation | 8 five-star characters, 51 four-star characters, 10 five-star weapons, 18 four-star weapons |
| Honkai: Star Rail | Stellar Warp | 7 five-star characters, 22 four-star characters, 7 five-star Light Cones, 31 four-star Light Cones |
| Zenless Zone Zero | Star-Studded Cast / An Outstanding Partner | 6 S-rank agents, 13 A-rank agents, 6 S-rank W-Engines, 24 A-rank W-Engines, 33 Bangboo |
| Honkai Impact 3rd | Dorm Supply | 41 S-rank battlesuits, 29 A/B-rank battlesuits |

HI3 named weapons, ELFs, and AstralOps are not part of the Dorm Supply pool, so
they are marked `false`.

The ZZZ catalog contains all 33 standard Bangboo. The four non-standard Bangboo
are `Luckyboo`, `Booressure`, `Bamboo`, and `Knightboo`.

## Source policy

`standard_pools.json` uses community-maintained pool pages as a machine-readable
reference:

- Genshin: `Wanderlust_Invocation`
- HSR: `Stellar_Warp`
- ZZZ: `Stable_Channel` and `Bangboo_Channel`
- HI3: `Dorm_Supply`

The linter and `apply_standard_pools --check` prevent the catalog from drifting
away from this file. After a major game update, verify the pool in-game and
update `standard_pools.json` in the same commit.
