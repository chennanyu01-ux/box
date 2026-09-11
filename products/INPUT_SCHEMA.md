# Shared input schema

All three product masters use one calculated JSON data package. Compute the chart once, then feed the same package to Mobile HTML, Desktop HTML and PDF so the three deliveries cannot disagree.

Required top-level fields:

- `meta`: `name`, `gender`, `birthplace`, `birth_local`, `true_solar`, `day_master`, `start_luck`, `direction`, `current_year`
- `bazi`: four strings in year / month / day / hour order
- profile text and 10-point labels: `summary`, `personality`, `industry`, `wealth`, `marriage`, `health`, `family` plus their `...Score` fields
- `chartPoints`: normally 100 annual records

Each annual record contains:

- `age`
- `year`
- `ganZhi`
- `daYun`
- `open`
- `close`
- `high`
- `low`
- `score`
- `reason`

The HTML masters derive career / wealth / relationship / noble-support lines dynamically from the day master, natal branches and annual/luck-cycle stems, then calibrate those component lines around the already calculated total annual score.

The JSON is the single source of truth for a customer order. Do not independently recalculate different numbers inside the three renderers.
