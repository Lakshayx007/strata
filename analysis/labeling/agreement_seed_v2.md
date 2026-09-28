### seed_v2: model_draft vs claude_review (model-vs-model agreement)

| Rows | Field | n | Agree | % agree | Cohen's kappa |
|---|---|---|---|---|---|
| all rows | taxonomy_code | 150 | 147 | 98.0% | 0.95 |
| all rows | from_vendor | 150 | 146 | 97.3% | 0.85 |
| all rows | to_vendor | 150 | 146 | 97.3% | 0.85 |
| all rows | direction | 150 | 148 | 98.7% | 0.95 |
| draft = none | taxonomy_code | 117 | 116 | 99.1% | n/a |
| draft = none | from_vendor | 117 | 117 | 100.0% | 1.00 |
| draft = none | to_vendor | 117 | 117 | 100.0% | 1.00 |
| draft = none | direction | 117 | 117 | 100.0% | 1.00 |
| draft = a reason | taxonomy_code | 33 | 31 | 93.9% | 0.92 |
| draft = a reason | from_vendor | 33 | 29 | 87.9% | 0.76 |
| draft = a reason | to_vendor | 33 | 29 | 87.9% | 0.74 |
| draft = a reason | direction | 33 | 31 | 93.9% | 0.90 |

Kappa is n/a where one rater used a single value in that subset (every draft row in 'draft = none' is none, so kappa cannot be computed there).

Per draft category (taxonomy_code):

| Category | Draft rows | Kept by reviewer | % kept | Reviewer rows |
|---|---|---|---|---|
| none | 117 | 116 | 99.1% | 118 |
| cost | 13 | 12 | 92.3% | 12 |
| performance_scale | 5 | 4 | 80.0% | 5 |
| lock_in_openness | 4 | 4 | 100.0% | 4 |
| right_sizing | 4 | 4 | 100.0% | 4 |
| operational_simplicity | 4 | 4 | 100.0% | 4 |
| other | 2 | 2 | 100.0% | 2 |
| ecosystem_fit | 1 | 1 | 100.0% | 1 |

Confusion table (rows: model_draft, columns: reviewer):

| model_draft \ reviewer | cost | ecosystem_fit | lock_in_openness | none | operational_simplicity | other | performance_scale | right_sizing |
|---|---|---|---|---|---|---|---|---|
| cost | 12 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| ecosystem_fit | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| lock_in_openness | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| none | 0 | 0 | 0 | 116 | 0 | 0 | 1 | 0 |
| operational_simplicity | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| other | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| performance_scale | 0 | 0 | 0 | 1 | 0 | 0 | 4 | 0 |
| right_sizing | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
