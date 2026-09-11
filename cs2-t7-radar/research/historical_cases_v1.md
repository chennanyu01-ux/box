# Historical pump cases v1

These are seed labels for model validation, not ground-truth proof of manipulation. The radar must not use future prices when scoring historical entry points.

| Item | Observed peak window | Rough move | Model role | Confidence |
|---|---|---:|---|---|
| Sticker | Evil Geniuses (Holo) | Stockholm 2021 | 2025-09 | extreme | benchmark supplied by user | high |
| Sticker | Mastermind (Holo) | 2025-10-06 | ~0.83 to 19.38 | strong positive: rapid supply squeeze | high |
| Sticker | Enemy Spotted (Holo) | 2025-10-07 | ~0.95 to 7.72 | strong positive: operation-sticker pump | high |
| Sticker | Gold Web (Foil) | 2025-12-27 | ~3.28 to 25.00 over 1y range | positive: older capped-supply sticker | medium |
| Sticker | Web Stuck (Holo) | 2026-03-11 | peak ~9.90 | positive / recurrence: multiple pump waves | medium |
| Sticker | Movistar Riders (Holo) | Stockholm 2021 | 2025-09-12 | ~8.46 to 57.41 over 1y range | same-regime sibling of EG; downweight for independence | medium |

## Validation policy

1. Separate manipulation/control score from T+7 entry score and distribution risk.
2. Use the first detectable pre-breakout window, not the eventual peak, as the positive label.
3. Downweight cases from the same collection/event wave so one coordinated market episode cannot dominate training.
4. Treat community reports as qualitative evidence only; price/listing history is primary.
5. Reject obvious bad ticks, ultra-illiquid single-sale spikes, and new-item launch price discovery unless independently confirmed across markets.
6. A historical case counts as useful only if a signal could have been produced with information available at that time.
