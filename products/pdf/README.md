# Life K-Line PDF v1.1

PDF canonical master. This version is a standalone archival product, separate from both HTML products. It is intended for direct delivery, long-term storage, printing, and customers who prefer a non-interactive copy.

The builder outputs a landscape A4 personal time atlas containing the 100-year K-line overview, decade and luck-cycle structure, a current-period zoom, peak/trough index, profile cards, chart basis, and a 100-year annual index.

## Structural rules

- Luck-cycle transition years such as `甲申 → 乙酉` are annual mixed-period labels, not separate luck cycles.
- Structural summaries assign a transition year to the period covering the larger share of that annual interval.
- The time-structure table uses dynamic row height and reserved vertical bounds so unexpected phase counts cannot overlap the decade cards or the phase chart.
- Decimal values are formatted before drawing; binary floating-point tails such as `12.509999999999998` must never appear in the delivered PDF.

Build with `python build_pdf.py --data input.json --out output.pdf`.

After generation, render every page for visual inspection. A successful script exit alone is not enough to approve the PDF product. Pay special attention to page 2 (time structure) and to the annual index when the input scores contain decimals.
