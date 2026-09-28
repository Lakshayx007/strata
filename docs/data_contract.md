# Data contract: `analysis/export/findings.json`

The frontend reads one file, `analysis/export/findings.json`. It is written by `python -m analysis.export.findings`
(Actions: `phase2` workflow, step `export_findings`, which commits the file) from the database and the committed
audit files. Do not edit it by hand. The narrative that goes with it is [findings.md](findings.md).

`schema_version` changes whenever a field is renamed, removed or changes meaning; adding a field does not change it.

## Conventions

- Counts are integers. Shares and rates are fractions between 0 and 1, rounded to 4 places (0.305 = 30.5%).
- Timestamps are ISO 8601 with a UTC offset. `null` means unknown or not applicable.
- `document_id` is `documents.id` in the database. `url` is the original public page.
- Vendor keys: `snowflake`, `databricks`, `google`, `aws`, `microsoft`, `cloudera`. Label vendor fields also use
  `other` (a named non-vendor tool) and `none`.
- Source keys: `hackernews`, `stackexchange`, `devto`, `github_threads`.
- Reason categories (`taxonomy_code`): `cost`, `operational_simplicity`, `lock_in_openness`, `performance_scale`,
  `right_sizing`, `ecosystem_fit`, `governance_security`, `other`, and `none` (no reason given). Definitions:
  `analysis/labeling/taxonomy.csv`.
- Directions: `adopt`, `leave`, `evaluate`, `none`.
- Labels are `claude_review` (a second model pass). **No label is human-reviewed**; the UI must not call them
  human, verified or ground truth.

## Top level

| field | type | meaning |
|---|---|---|
| `schema_version` | int | currently 1 |
| `generated_at` | string | when the export ran |
| `label_set` | string | the label set every label count uses: `claude_review` |
| `human_reviewed_labels` | int | labels with `labeled_by='human'`; 0 |
| `corpus` | object | corpus size, below |
| `share_of_voice` | array | one row per vendor, largest first |
| `reasons` | object | reason counts from the labelled samples |
| `agreement` | array | model_draft vs claude_review agreement |
| `promotional_sensitivity` | object | reason counts with and without documents flagged as promotional |
| `quotes` | array | verbatim quotes to display |
| `cloudera` | object | Cloudera documents and cases |
| `deployment_control_probe` | object | totals from the audit of a proposed category that was not added |

## `corpus`

| field | type | meaning |
|---|---|---|
| `discussion_documents` | int | documents from the four discussion sources |
| `discussion_documents_by_source` | {source: int} | the same by source |
| `vendor_documents` | int | discussion documents naming at least one vendor (the share-of-voice denominator) |
| `switching_vendor_documents` | int | of those, documents with switching language (v1 phrase list) |

## `share_of_voice[]`

| field | type | meaning |
|---|---|---|
| `vendor` | string | vendor key |
| `documents` | int | discussion documents naming the vendor (a document can name several) |
| `share_of_vendor_documents` | float | `documents / corpus.vendor_documents`; shares sum to more than 1 |
| `mentions` | int | total matched mentions |
| `switching_documents` | int | documents naming the vendor with switching language (v1 phrase list) |
| `reason_v2_documents` | int | documents naming the vendor that detector v2 flags as possibly reason-bearing |
| `documents_by_source` | {source: int} | `documents` split by source |

Display note: Cloudera's Dev.to count is not comparable (no Cloudera tag in the Dev.to feeds).

## `reasons`

| field | type | meaning |
|---|---|---|
| `documents_labelled` | int | documents in seed_v1 + seed_v2 (300) |
| `reasons_total` | int | labelled documents whose `taxonomy_code` is not `none` |
| `by_category[]` | array | `{category, reasons, by_source: {source: int}, by_sample: {sample: int}}`, largest first |
| `by_source[]` | array | `{source, documents, with_reason, with_move, reason_share}` |

`with_move` counts documents whose direction is not `none`. The samples over-draw switching-language documents, so
these counts describe the labelled documents, not the corpus.

## `agreement[]`

`{sample, field, n, agree, pct_agree, cohen_kappa, raters}` for `field` in `taxonomy_code` and `direction`. `raters`
is always `["model_draft", "claude_review"]`: this is model-vs-model agreement, not accuracy.

## `promotional_sensitivity`

Two variants with the same shape: `seed_v2` drops the documents the seed_v2 review notes flag as vendor or
self-promotional; `all_samples` also drops those flagged in the seed_v1 notes. Each has
`flagged_document_ids`, `flagged_with_reason`, `reasons_with`, `reasons_without`,
`by_category[] = {category, with, without}`, `rank_order_with` and `rank_order_without` (category keys, largest
first; ties broken alphabetically). The flag is not part of the pipeline; the labels are unchanged.

## `quotes[]`

| field | type | meaning |
|---|---|---|
| `document_id` | int | source document |
| `category` | string | the document's `claude_review` reason category |
| `quote` | string | verbatim text (checked against the stored document at export; may be part of a sentence) |
| `source`, `url`, `posted_at` | | where and when it was posted |
| `sample` | string | `seed_v1` or `seed_v2` |
| `from_vendor`, `to_vendor`, `direction` | string | the document's `claude_review` label |

Show the quote exactly as given, with its link.

## `cloudera`

| field | type | meaning |
|---|---|---|
| `documents` | int | discussion documents naming Cloudera (Hortonworks counts as Cloudera) |
| `by_source` | {source: int} | by source |
| `by_year` | {year: int} | by year posted; not normalised for how many documents each year has in the corpus, so do not plot it as a trend |
| `labelled` | int | of those, documents in a labelled sample |
| `labelled_with_reason` | int | labelled documents with any reason (the reason need not be about Cloudera) |
| `labelled_leaving_cloudera` | int | labelled documents with `from_vendor = cloudera` |
| `cases[]` | array | `{document_id, kind, source, url, title, posted_at, quotes[]}`; `kind` is `stranded_on_free_edition`, `exit_to_open_source` or `legacy_reference`; quotes are verbatim |
| `document_list[]` | array | every Cloudera document, oldest first: `{document_id, source, url, title, posted_at, other_vendors[], switching_v1, sample, taxonomy_code, direction, from_vendor}`; the last four are `null` for unlabelled documents |

## `deployment_control_probe`

`{strict_documents_audited, deployment_control_reason, overlaps_other_category, not_a_reason, decision}`, the
totals of `analysis/labeling/probe_deployment_control_audit.csv`. `decision` is `not_added`.
