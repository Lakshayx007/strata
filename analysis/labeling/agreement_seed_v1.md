### seed_v1: model_draft vs claude_review (model-vs-model agreement)

| Rows | Field | n | Agree | % agree | Cohen's kappa |
|---|---|---|---|---|---|
| all rows | taxonomy_code | 150 | 142 | 94.7% | 0.85 |
| all rows | from_vendor | 150 | 147 | 98.0% | 0.88 |
| all rows | to_vendor | 150 | 145 | 96.7% | 0.87 |
| all rows | direction | 150 | 144 | 96.0% | 0.85 |
| draft = none | taxonomy_code | 121 | 116 | 95.9% | n/a |
| draft = none | from_vendor | 121 | 120 | 99.2% | 0.66 |
| draft = none | to_vendor | 121 | 117 | 96.7% | 0.49 |
| draft = none | direction | 121 | 117 | 96.7% | 0.42 |
| draft = a reason | taxonomy_code | 29 | 26 | 89.7% | 0.88 |
| draft = a reason | from_vendor | 29 | 27 | 93.1% | 0.89 |
| draft = a reason | to_vendor | 29 | 28 | 96.6% | 0.95 |
| draft = a reason | direction | 29 | 27 | 93.1% | 0.90 |

Kappa is n/a where one rater used a single value in that subset (every draft row in 'draft = none' is none, so kappa cannot be computed there).

Per draft category (taxonomy_code):

| Category | Draft rows | Kept by reviewer | % kept | Reviewer rows |
|---|---|---|---|---|
| none | 121 | 116 | 95.9% | 119 |
| cost | 8 | 7 | 87.5% | 8 |
| operational_simplicity | 6 | 5 | 83.3% | 7 |
| lock_in_openness | 4 | 4 | 100.0% | 4 |
| ecosystem_fit | 4 | 3 | 75.0% | 3 |
| governance_security | 2 | 2 | 100.0% | 2 |
| performance_scale | 2 | 2 | 100.0% | 3 |
| right_sizing | 2 | 2 | 100.0% | 3 |
| other | 1 | 1 | 100.0% | 1 |

Confusion table (rows: model_draft, columns: reviewer):

| model_draft \ reviewer | cost | ecosystem_fit | governance_security | lock_in_openness | none | operational_simplicity | other | performance_scale | right_sizing |
|---|---|---|---|---|---|---|---|---|---|
| cost | 7 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| ecosystem_fit | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| governance_security | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| lock_in_openness | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| none | 1 | 0 | 0 | 0 | 116 | 2 | 0 | 1 | 1 |
| operational_simplicity | 0 | 0 | 0 | 0 | 1 | 5 | 0 | 0 | 0 |
| other | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| performance_scale | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| right_sizing | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
