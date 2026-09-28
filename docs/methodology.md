# Strata methodology

This file records the collection and counting decisions a reviewer would need to judge whether a Strata number is
defensible. It is updated whenever one of those decisions changes.

## Two kinds of evidence, never mixed

Strata stores two different kinds of evidence, and they answer different questions.

| | `documents` (+ `mentions`) | `signals` |
|---|---|---|
| What it is | Text a practitioner wrote: a Reddit post or comment, an HN story or comment, a Stack Overflow question, a vendor page | A count over time: Stack Overflow questions per tag per month, GitHub stars, contributors, issues opened and closed |
| What it measures | **Stated reasoning.** Why people say they chose, left or evaluated a platform | **An adoption or activity proxy.** How much activity surrounds a technology |
| Unit | One document | A number with a unit (`questions`, `stars`, `issues`, `contributors`) |

**Rule:** signals and documents are never aggregated into the same metric, added together, or used to normalise each
other without saying so explicitly. A chart may show both side by side, but each keeps its own axis and caption. For
example, "Snowflake: 1,200 SO questions + 340 discussions" is not allowed. Tag counts measure how many people needed
help, and discussions measure what people argued about. Adding them produces a number with no meaning.

This is enforced structurally. The two live in separate tables, and `signals` has no `document_id`.

## Sources and access rules

- Collection uses official APIs, plus robots-permitted public pages for vendor pricing and docs only. G2, Gartner
  Peer Insights, TrustRadius and any site whose terms prohibit automated collection are out of scope and will not be
  added.
- Every request sends `strata-research/0.1 (+https://github.com/Lakshayx007/strata; portfolio research project)`.
- Every adapter throttles itself to the documented rate limit. On 429 or 5xx it backs off exponentially, and a
  `Retry-After` header wins when present. Stack Exchange's `backoff` field is honoured, and a persistent daily
  budget keeps unkeyed use under 300 requests.
- **robots.txt applies only to `vendor_docs.py`.** robots.txt governs crawlers on web pages, not documented API
  access, so applying it to `hn.algolia.com`, `api.stackexchange.com` or `oauth.reddit.com` would produce false
  blocks. For vendor pages, an unreachable, 401/403 or 5xx robots.txt means the host is treated as off-limits, and a
  4xx (other than 401/403) means no restrictions (RFC 9309).
- **Reddit is excluded.** Creating an API app now requires approval under Reddit's Responsible Builder Policy,
  which this project does not have. No unauthenticated JSON endpoints or old.reddit scraping are used as a
  workaround. The sources table carries the row with that note, so the gap is visible.
- Replacement volume comes from keyless official APIs:
  - Stack Exchange: Stack Overflow, plus dba, datascience and softwareengineering. The smaller sites are searched
    by full text because their tags differ.
  - Dev.to tag feeds. On the broad tags, dataengineering and lakehouse, an article body is fetched only when its
    title, description or tags name a vendor or lakehouse technology.
  - GitHub issues and discussions. These are searched only for migration and comparison phrases.
- GitHub calls use the Actions token, or a no-scope classic token when run locally.
- `sources.terms_note` records what each source's terms permit at the time of collection.

## What becomes a document

- HTML is stripped to plain text once, in `normalize.py`.
- A link-only post uses its title as the body, so what was actually said is never dropped.
- `[deleted]` and `[removed]` placeholders are not documents.
- Reddit comment trees are flattened, and each comment is one document with a link to its submission.
- Vendor pages have `posted_at` set to NULL unless the server sends `Last-Modified`. A fetch date is not a publication
  date.

## Author privacy

Authors are stored only as `HMAC-SHA256(AUTHOR_HASH_SALT, "<source>:<author>")`, truncated to 24 hex characters. The
salt comes from `.env` and is never committed. With a committed salt, anyone could hash a known username and reverse
the mapping. The hash exists so that one prolific poster dominating a theme can be detected.

## Deduplication

1. **Exact:** `content_hash` = SHA-256 of the lower-cased, whitespace-collapsed body. The same text posted twice is
   one document, and the earliest post is kept. It is also a unique index, so the rule holds across runs.
2. **Near-duplicate:** word 3-shingles, cosine similarity >= 0.90, checked against earlier documents in the batch
   and against every document already loaded. Texts under 30 words are exempt: two short "we moved to X" comments
   from different people are separate voices.
Every dropped document is recorded in the `dedupe_drops` table (and a local CSV) with the document it duplicated and
the similarity score. The duplicate rate is dropped / (dropped + kept). Drops are unique per source item, so
re-running an ingestion does not inflate it.

## Mention matching

Mention matching is regex-based, and all patterns live in `ingestion/config.py`.

1. **Unambiguous aliases** are always counted (e.g. `databricks`, `bigquery`, `azure synapse`, `aws glue`).
2. **Ambiguous words** are counted only when a context pattern appears within a character window:
   - `redshift`: astronomy.
   - `synapse`: neuroscience.
   - `delta`: a generic difference or change.
   - `spark`: the generic verb.
3. **Excluded patterns** are never counted:
   - `snowflake schema`: a dimensional-modelling term.
   - Bare `fabric` and bare `glue`: ordinary English. They count only through product phrases such as
     `fabric lakehouse` or `glue catalog`.

Every rejected candidate is logged per term, and written with a text snippet to
`data/processed/rejected_mentions.csv`. Precision can therefore be audited by reading what was thrown away.

Entities prefixed `tech:` (`tech:delta_lake`, `tech:apache_spark`) are open-source technologies, not vendors. They
are recorded in `mentions`, but are never attributed to a vendor and are excluded from vendor charts. Delta Lake is
not Databricks.

`first_char_offset` indexes into `body`. It is NULL when the entity appears only in the title.

## Switching language and corpus readiness

A document "contains switching language" if its **body** matches any phrase in `config.SWITCHING_PHRASES`. The match
is case-insensitive and on whole words, so "POC" does not match "epoch". The phrases are: migrated from, moved off,
switched to, moving from, instead of, evaluated, bake-off, bakeoff, POC, proof of concept, ripped out, replaced with,
consolidated onto. A wider list (`SWITCHING_SEARCH_PHRASES`) is used only at search time to improve recall. It never
feeds a reported count.

A document is **multi-vendor** if it mentions two or more distinct vendors. `tech:` entities do not count. Headline
readiness numbers from `python -m analysis.report` cover the discussion sources only (HN, Stack Exchange, Dev.to, GitHub threads),
because vendor pages are reference text and are not seed material.

## Signals

| signal_type | entity | metric(s) | notes |
|---|---|---|---|
| `so_tag_count` | vendor slug | `questions:<tag>` | One metric per tag. AWS and Microsoft have two tags each, and a question can carry both, so tags are not summed. Only complete months are collected. |
| `gh_stars` | `owner/repo` | `new_stars`, `cumulative_stars` | Built from stargazer `starred_at`. Users who later unstarred are not visible, so cumulative stars slightly understate historical peaks. Months with no stars are recorded as 0. The current month is partial. |
| `gh_contributors` | `owner/repo` | `contributors_incl_anon_snapshot` | A point-in-time snapshot taken on the fetch date, not a monthly flow. |
| `gh_issue_velocity` | `owner/repo` | `issues_opened`, `issues_closed` | Pull requests are excluded. Months before `STRATA_SINCE` are dropped because the API filters on update time, which makes them incomplete. |

## Honest gaps

A source that returns nothing, or cannot run, stays empty and is reported as such. Nothing is synthesised or
back-filled, and the EDA notebook's coverage table shows every source, including those with zero rows.

# Phase 2: seed sample and labelling

## Limitation: no human review

**No label in this project has been reviewed by a human.** Every label is either a first-pass model draft
(`labeled_by='model_draft'`) or a second pass by a separate Claude session that saw excerpts only
(`labeled_by='claude_review'`). The `human_check` column in the seed_v2 workbook was intentionally left blank.
All "agreement" figures are therefore model-vs-model: they measure consistency between two passes of similar
models, not accuracy, and shared blind spots would not show up in them. Category counts and detector precision
figures inherit that limitation and should be read as model-labelled estimates.

## Seed sample (`seed_v1`)

`python -m analysis.labeling.sample` (or the **phase2** workflow, step `sample`) draws 150 discussion documents with
a fixed seed (20260925) and records the draw in `sample_members`, so a re-run returns the same documents even after
the corpus grows.

- **Pool:** Hacker News, Stack Exchange and Dev.to documents with at least 20 words that name at least one of the six
  vendors (`tech:` entities do not count). GitHub issues and discussions are not in the seed quota.
- **Quotas:** HN 60, Stack Exchange 45, Dev.to 45, so HN does not dominate.
- **Switching weight:** at least 110 of 150 use switching language (the Phase 1 phrase list), set per source in
  proportion to its quota.
- **Vendor floors:** at least 12 documents naming Cloudera and at least 10 each for Microsoft, AWS and Google. Floors
  are filled first, scarcest vendor first, switching documents first, spread across sources.

Achieved on 2026-09-25 (phase2 run 36173630209):

| | Target | Achieved |
|---|---|---|
| Total | 150 | 150 |
| Switching language | ≥ 110 | 110 |
| HN / Stack Exchange / Dev.to | 60 / 45 / 45 | 60 / 45 / 45 (switching 44 / 33 / 33) |
| Cloudera | ≥ 12 | 12 |
| Microsoft | ≥ 10 | 19 |
| AWS | ≥ 10 | 32 |
| Google | ≥ 10 | 36 |
| Databricks / Snowflake | – | 46 / 72 |
| Multi-vendor documents | – | 39 |

34 of the 150 were picked to meet a vendor floor (Cloudera 12, Microsoft 9, Google 7, AWS 4); the rest were drawn
at random within the source quotas. The floors therefore over-represent the smaller vendors relative to the corpus,
so seed-sample label frequencies must not be read as market-wide frequencies.

## Finding: Cloudera's share of voice

Across the 12,056 discussion documents (HN, Stack Exchange, Dev.to, GitHub threads) on 2026-09-25, 6,086 name at
least one vendor. Documents naming each vendor, as a share of those 6,086 (a document can name several):

| Vendor | Documents | Share | Mentions | Switching-language documents | Share of 791 |
|---|---|---|---|---|---|
| Snowflake | 2,009 | 33.0% | 15,410 | 371 | 46.9% |
| Databricks | 1,687 | 27.7% | 10,468 | 245 | 31.0% |
| Google | 1,376 | 22.6% | 5,477 | 168 | 21.2% |
| AWS | 1,122 | 18.4% | 4,260 | 148 | 18.7% |
| Microsoft | 678 | 11.1% | 3,233 | 66 | 8.3% |
| **Cloudera** | **55** | **0.9%** | **118** | **7** | **0.9%** |

Cloudera appears in 55 documents, about 1 in 37 of Snowflake's volume, and in only 7 switching-language documents.
On HN and Stack Exchange, Cloudera had the same search budget as Databricks, Snowflake and Google (one base term,
crossed with the same switching phrases, plus the `cloudera` Stack Overflow tag), and it still appears in 30 HN and
19 Stack Exchange documents against 722 to 1,052 HN documents for each of those three. That gap is a finding: in
public practitioner discussion since 2023, Cloudera is close to absent from lakehouse platform choice.

Caveats a reader should see alongside the number:
- **Dev.to is not a fair comparison for Cloudera.** The Dev.to feeds (`config.DEVTO_TAGS`) include tags for
  Databricks, Snowflake, BigQuery and Redshift but none for Cloudera, so its 3 Dev.to documents understate it there.
- The sources skew toward cloud-native and developer audiences, where on-premises Hadoop estates are discussed less.
- "Hortonworks" is counted as Cloudera, so the figure is not lowered by the merger.
- Cloudera findings from the seed sample rest on 12 documents.
- The table above uses the Phase 1 matcher. The recomputed figures after the Snowflake fix (2026-09-28) are in
  "Snowflake disambiguation and recomputed share of voice" below; Cloudera is unchanged at 55 documents (0.9%).

## Draft taxonomy and pre-labels (`model_draft`)

The eight draft categories and 150 pre-labels were written by the model after reading the sample, and are stored
as `labeled_by='model_draft'`. They are not ground truth. The files are `analysis/labeling/taxonomy.csv` (formerly
`taxonomy_draft.csv`) and `analysis/labeling/draft_labels_seed_v1.csv` (formerly `draft_labels.csv`), and the review workbook is `analysis/labeling/seed_review.xlsx`. Every example
quote and evidence sentence is checked by `build_review.py` (and again by `load_labels.py` against the database) to
be verbatim text of its document. The build fails otherwise.

What the draft pass found about the sample itself:

- **Most switching-language matches are not switching.** Of the 110 documents flagged by the phrase list, 22 state
  a reason for choosing, leaving or evaluating a platform. "Instead of" and "evaluated" match ordinary prose and
  how-to questions. On Stack Exchange, 2 of 33 flagged questions state a reason. The phrase list is a recall filter,
  not a measure of switching discussion, and no reported number should treat it as one.
- **Dev.to carries most of the stated reasoning** (13 of 45 documents), but much of it is vendor or consultancy
  content (Chaos Genius, MotherDuck, PipeCode, Hexaview). Source authorship should be a column in Phase 3.
- **"snowflake" has false positives on HN.** At least 7 HN documents use "snowflake" in its non-vendor sense ("special
  snowflake", a political insult, "snowflake model"). The mention matcher needs a context rule for bare
  "snowflake", like the ones already used for redshift and synapse.

## Taxonomy decision (2026-09-28)

All categories were kept except `skills_team`, which merged into `operational_simplicity` (now named "Operational
simplicity and operating model"; its definition covers the team's skills and operating model). The two drafts
coded `skills_team` (documents 8703 and 11149) were recoded in the draft file, so seed_v1 now has seven reason
categories plus the utility codes `other` and `none`. The round-1 workbook `seed_review.xlsx` is kept as sent and
still shows `skills_team`.

## Second review pass (`claude_review`) and model-vs-model agreement

**Who reviewed.** The `my_` columns of the returned workbook were filled by a second Claude session that saw only
the ~60-word excerpts and the links, not by a person. Its rows are stored as `labeled_by='claude_review'`
(`analysis/labeling/claude_review_labels_seed_v1.csv`, workbook `seed_review_claude_review.xlsx`). A blank `my_` cell
keeps the draft value. **No seed_v1 label is human.** Every number below is agreement between two model passes, not
a validation against a person, and two model passes can share the same blind spots. It shows the draft labels are
consistent under a second reading; it does not show they are right.

Computed by `python -m analysis.labeling.review` after applying the taxonomy merge to both sides, so the merge is not
counted as disagreement. Rows are split by whether the draft gave a reason, because 121 of 150 drafts are `none` and
would otherwise dominate the headline.

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


Headline: the two passes agree on the reason code for 142 of 150 documents (94.7%, kappa 0.85). On the 29 documents
where the draft gave a reason, 26 match (89.7%, kappa 0.88). The reviewer moved five `none` drafts to a reason
(989, 1010, 2110, 10994, 11092) and three reason drafts to `none` (7853, 8703, 12516).

### Rows the reviewer flagged for a full-text check

The reviewer only saw excerpts, so four rows it marked "LOW CONFIDENCE" or "Check the full text" were read in full:

- **989** (HN). Argues for a "snowflake approach": one enterprise data layer, transforming centrally rather than in
  each downstream system, with flexible access and performance. The vendor reading is plausible (data context), but
  no platform move is reported. The reviewer's `operational_simplicity` fits the argument; direction stays `none`.
- **1010** (HN). Argues for PostgreSQL by default (free, runs anywhere, no budget approval, one stack from tiny to
  large) and says requirements could send a team to Snowflake, Redis or DynamoDB. A stated preference, not a move.
  The reasons mix cost and flexibility; the reviewer's `right_sizing` is a fair reading.
- **12498** (Dev.to, a Hexaview vendor blog). The legacy systems named are "Teradata, Netezza, or Oracle". There is
  no Hadoop or Cloudera mention, so `from_vendor` stays `other`, not `cloudera`. Reasons given: cost to maintain,
  data variety and volume, proprietary lock-in. It is vendor marketing, not a practitioner account.
- **78** (HN). An essay on open-source go-to-market (Amplitude pricing, AWS for startups, Snowflake vs Databricks and
  open source). Databricks and Snowflake are correct company matches, but no platform choice is described; `none`.

### Vendor-match check on rows noted "NOT THE VENDOR" or "Off-topic"

Correct vendor matches: 694, 706 (Variant type proposals), 910, 1119 (the Snowflake breach), 1351 (Snowflake as an
OpenTelemetry maintainer). False "snowflake" matches: 895 ("snowflake status"), 903 ("they're a snowflake"), 905
("being called a snowflake"), 929 ("snowflake model"), 942, 1364 and 1394 ("special snowflake"), 1545 ("fresh
snowflake"). These eight are the test cases for the Snowflake disambiguation rule below.

## Snowflake disambiguation and recomputed share of voice (2026-09-28)

**Rule.** Bare "snowflake" is now an ambiguous term (`config.AMBIGUOUS_TERMS`), like "redshift" and "synapse":

- A capitalised "Snowflake" counts as the vendor.
- A lowercase "snowflake" counts only with data context within 200 characters (warehouse, SQL, query, data, dbt,
  Databricks, BigQuery, column, procedure, connector, Snowpark and similar; the full list is in the config).
- Known other senses never count, whatever the case (`config.EXCLUDED_PATTERNS`): "special/unique/fragile snowflake",
  the insult ("called a snowflake", "you're such a snowflake", plural "snowflakes"), "its own snowflake", snowflake
  schema/model/dimension, snowflake servers and IDs (Twitter's ID scheme), the Koch snowflake, Tor's Snowflake proxy,
  the novel-writing "snowflake method", and Snowflake Bentley.
- A title now takes its context from the document body as well as from the title itself.
- Snowpark, Snowpipe, SnowSQL, Snowflake Cortex and snowflake.com always count.

On seed_v1 the rule removes exactly the eight false matches the review flagged (895, 903, 905, 929, 942, 1364, 1394,
1545) and changes nothing else about Snowflake.

**How it was checked on the corpus.** Rebuilding mentions (`python -m analysis.labeling.recompute_mentions`) logs every
document-vendor pair that changes, and `python -m analysis.labeling.audit_mentions --entity snowflake` lists every
document containing "snowflake" that is no longer counted, with the matcher's reason and snippet. The first version of
the rule (lowercase or sentence-initial needs context) was too strict: the audit showed it dropped real vendor
headlines ("Snowflake CEO Frank Slootman Retires", "Snowflake Copilot") and Stack Exchange questions ("setup snowflake
task to run every 2nd Monday of the month"). It was corrected before any number was recorded. In the final audit, 309
documents contain "snowflake" but are not counted. Reading every snippet, about 6 of them are the vendor and are
still missed (for example "the snowflake event" at Moscone Center, "internal to snowflake?"). Among documents the
rule accepts, a handful of non-vendor uses remain (for example a quoted insult, "Snowflake", and "snowflake features"
of a Rust variant). Both error counts are small next to the 197 false matches removed.

**Side effect.** Because titles now take context from the body, Stack Exchange questions that name "Redshift" or
"Synapse" in the title only are now counted: AWS gains 44 documents and Microsoft 9.

**Recomputed share of voice** (12,056 discussion documents; 5,941 name a vendor, down from 6,086; 748 of those use
v1 switching language, down from 791):

| Vendor | Documents (was) | Share (was) | Mentions | Switching-language documents | Reason-bearing (v2) |
|---|---|---|---|---|---|
| Snowflake | 1,812 (2,009) | 30.5% (33.0%) | 14,969 | 326 | 626 |
| Databricks | 1,687 (1,687) | 28.4% (27.7%) | 10,468 | 245 | 548 |
| Google | 1,376 (1,376) | 23.2% (22.6%) | 5,477 | 168 | 399 |
| AWS | 1,166 (1,122) | 19.6% (18.4%) | 4,403 | 150 | 342 |
| Microsoft | 687 (678) | 11.6% (11.1%) | 3,289 | 66 | 146 |
| Cloudera | 55 (55) | 0.9% (0.9%) | 118 | 7 | 15 |

Snowflake stays first, but its lead over Databricks narrows from 5.3 to 2.1 points of vendor-naming documents.
Almost all of the change is on HN, which loses 195 Snowflake documents (Stack Exchange and Dev.to lose one each);
Snowflake still leads Databricks on HN, 857 to 815. The seed_v1 sample was drawn with the old matcher and is left as
drawn; its Snowflake coverage falls from 72 to 64 documents.

## Switching detector v2 (2026-09-28)

The v1 phrase list (`config.SWITCHING_PHRASES`) stays unchanged so earlier switching counts remain comparable.
Detector v2 (`normalize.has_reason_language`) works per sentence: a sentence qualifies when it names a data platform
(`config.PLATFORM_TERMS`, which includes non-vendor platforms such as Postgres, DuckDB, Teradata and Hadoop) and
either reports a move or comparison (`config.MOVE_PHRASES`) or gives a reason (`config.REASON_CUES`, one group of cue
words per taxonomy category).

Measured against the seed_v1 `claude_review` labels (`python -m analysis.labeling.detector_eval`), where a document is
positive when the reviewer gave a reason or a move (33 of 150):

| Detector | Flagged | True positives | Precision | Recall |
|---|---|---|---|---|
| v1 phrase list | 110 | 27 | 24.5% | 81.8% |
| v2 platform + move/reason sentence | 84 | 27 | 32.1% | 81.8% |

Three reasons these numbers flatter both detectors, so they must not be quoted as corpus precision or recall:
- v2 was tuned on seed_v1, so its seed_v1 score is optimistic.
- seed_v1 was drawn so that 110 of 150 documents match v1, so positives that v1 misses are under-represented and v1's
  recall is overstated.
- The labels are a second model pass, not a human one.
seed_v2 gives a fresh test: once it is reviewed, both detectors will be scored on it. v2 still misses reasons stated
without naming a platform in the same sentence (989, 2156, 10994, 11092) and moves described without a reason word
or move verb (6711, 8134).

## Seed sample `seed_v2` (2026-09-28)

Drawn by `python -m analysis.labeling.sample --sample seed_v2` after the mention recompute, with seed 20260928. It uses
the same pool rules, quotas (HN 60, Stack Exchange 45, Dev.to 45) and vendor floors as seed_v1, with two changes:
every seed_v1 document is excluded, and detector v2 replaces the phrase list as the priority flag (at least 120
flagged). Within flagged documents, those with a sentence that both reports a move and gives a reason are taken first.

| | seed_v1 | seed_v2 |
|---|---|---|
| Documents | 150 | 150 |
| v1 phrase list matches | 110 | 47 |
| Detector v2 matches | 84 | 120 |
| A sentence with a move and a reason | 23 | 74 |
| Multi-vendor | 39 | 32 |
| HN / Stack Exchange / Dev.to (flagged) | 60 (44) / 45 (33) / 45 (33) | 60 (48) / 45 (36) / 45 (36) |
| Databricks / Snowflake / Cloudera / AWS / Microsoft / Google | 46 / 64 / 12 / 32 / 19 / 36 | 41 / 55 / 12 / 37 / 13 / 34 |

All vendor floors are met (Cloudera 12, Microsoft 13, AWS 37, Google 34). seed_v2 deliberately over-samples
reason-bearing documents, so category shares in it are not corpus shares; they are for building and testing the
taxonomy.


## seed_v2 draft labels (`model_draft`, 2026-09-28)

The 150 seed_v2 documents were pre-labelled by the model (`analysis/labeling/draft_labels_seed_v2.csv`) with the
approved taxonomy and the same rules as seed_v1. The review workbook is `analysis/labeling/seed_v2_review.xlsx`:
rows with a draft reason come first, then rows that only report a move. The workbook has a `human_check` column,
which was intentionally left blank: there is no human review in this project (see "Limitation" above).

What the draft pass found, before any review:

- **33 of 150 drafts give a reason** (seed_v1: 29), and 20 report a move or an evaluation. Drawing reason-bearing
  documents first helped less than the detector flags suggested.
- **By detector tier** (draft reason or move / documents): a sentence with both a move and a reason 30 / 74 (41%),
  detector v2 only 7 / 46 (15%), not flagged 1 / 30. So v2's precision on this fresh sample is about 31% (37 of 120)
  by the drafts, close to its 32% on seed_v1. These are draft labels, so the figure is provisional until reviewed.
- **Stack Exchange gives no reasons at all** (0 of 45; three report a migration to Snowflake without saying why).
  Hacker News gives 25 of 60, Dev.to 8 of 45. Most Dev.to documents flagged by v2 are vendor, consultancy or
  training content that names costs and features without describing a platform choice.
- Cost is again the most common reason (13), then performance and scale (5).

## Pooled reason counts, seed_v1 + seed_v2 (2026-09-28)

`python -m analysis.labeling.pool` writes `analysis/labeling/pooled_reasons.md`. It uses the `claude_review` set
where one exists and the `model_draft` set otherwise. Both samples now use `claude_review`. No label is human.

63 reasons in 300 documents:

| category | seed_v1 | seed_v2 | total | Hacker News | Dev.to | Stack Exchange |
|---|---|---|---|---|---|---|
| cost | 8 | 12 | 20 | 15 | 5 | 0 |
| operational_simplicity | 7 | 4 | 11 | 7 | 4 | 0 |
| lock_in_openness | 4 | 4 | 8 | 2 | 6 | 0 |
| performance_scale | 3 | 5 | 8 | 5 | 2 | 1 |
| right_sizing | 3 | 4 | 7 | 7 | 0 | 0 |
| ecosystem_fit | 3 | 1 | 4 | 0 | 4 | 0 |
| other | 1 | 2 | 3 | 3 | 0 | 0 |
| governance_security | 2 | 0 | 2 | 1 | 1 | 0 |
| **total** | 31 | 32 | 63 | 40 | 22 | 1 |

By source, 40 of 120 Hacker News documents give a reason (33%), 22 of 90 Dev.to (24%) and 1 of 90 Stack Exchange
(1%). Stack Exchange asks how, not why, so it contributes almost nothing to reason counts. Cost and right-sizing
reasons come mostly from Hacker News; lock-in and ecosystem reasons mostly from Dev.to. With 63 reasons in total,
categories below about 10 are too small to rank against each other.

## Proposed category `deployment_control`: not added (2026-09-28)

The seed_v2 review proposed a category for choosing where a platform runs (self-hosted, bring-your-own-cloud,
customer-managed VPC, on-prem, data residency). `python -m analysis.labeling.category_probe` (Actions `phase2`,
step `probe_category`) counts cue sentences over all 12,056 discussion documents, using the existing categories'
cue lists as a yardstick. "Strict" means a cue, a platform term and a move phrase in the same sentence.

| category | documents with cue | strict | strict HN | strict SE | strict Dev.to | strict GitHub |
|---|---|---|---|---|---|---|
| cost | 1,719 | 106 | 32 | 1 | 70 | 3 |
| performance_scale | 1,824 | 76 | 16 | 3 | 54 | 3 |
| operational_simplicity | 1,661 | 51 | 13 | 0 | 36 | 2 |
| ecosystem_fit | 938 | 46 | 7 | 3 | 32 | 4 |
| governance_security | 1,143 | 43 | 5 | 0 | 37 | 1 |
| lock_in_openness | 516 | 28 | 8 | 0 | 20 | 0 |
| **deployment_control** | 302 | 27 | 9 | 1 | 17 | 0 |
| right_sizing | 33 | 0 | 0 | 0 | 0 | 0 |

Every one of the 27 strict documents was read (`analysis/labeling/probe_deployment_control_audit.csv`):
**3 are a deployment-control reason** (919, 2116, 3688), 6 mention deployment but the reason is cost, lock-in or
operational simplicity (105, 3276, 7118, 11019, 11078, 11150), and 18 are not a reason at all. Most of those 18 describe
on-prem-to-cloud migrations, the opposite of the proposed category. In the 300 labelled seed documents only one
reason (2116) fits it. Strict documents name Snowflake 12, Databricks 12, AWS 7, Cloudera 2, Google 2, Microsoft 1.

**Recommendation: do not add it.** Three real cases in the full corpus is too few to count, and most mentions
already fit cost, lock-in or operational simplicity. Code the rare pure cases as `other` with a note, and keep the
cue list in `category_probe.py` so the question can be re-run if new sources change the picture. (The cue probe
also finds no strict `right_sizing` documents, but that category is kept on label evidence, 7 reasons, because its
cue list is only the word "overkill".)

## Qualitative finding: Cloudera free-edition upgrade path (doc 7279)

Document 7279 (Stack Overflow, 2023-09-20, "Cloudera Enterprise (Community Edition) for RHEL 8",
https://stackoverflow.com/questions/77139887) is a single case, recorded as a qualitative finding rather than a
count. The asker's team runs "a mini DWH platform with Cloudera Enterprise community version" (Cloudera Express
6.0.1) on RHEL 7, must move to RHEL 8, and is "not able to find any upgraded version of Cloudera Enterprise which
supports RHEL 8". They "want to stay on Community edition of Cloudera" and describe the information on Cloudera's
community site as "not very much clear". The draft label is `none` (no platform choice is made yet).

What it shows: a team on Cloudera's free edition has an operating-system upgrade forced on it and cannot find a
supported path that keeps them on the free edition. That is a retention risk that arrives through a platform
mandate rather than through a comparison with a competitor. It is one document out of 55 that mention Cloudera,
so it illustrates a possible pattern and does not measure one. No claim about Cloudera's licensing or support
policy is made here; only what the asker wrote.

## seed_v2 second review (`claude_review`) and model-vs-model agreement (2026-09-28)

The seed_v2 workbook came back as `analysis/labeling/seed_v2_review_claude_review.xlsx` (150 rows). Its `my_`
columns and notes were filled by a separate Claude session that saw excerpts only, so they are stored as
`labeled_by='claude_review'` (`claude_review_labels_seed_v2.csv`). `human_check` is blank in every row; see
"Limitation: no human review". A blank `my_` cell keeps the draft value.
`python -m analysis.labeling.review --sample seed_v2 ... --labeled-by claude_review` writes `agreement_seed_v2.md`.

| field | all 150 rows | kappa | 33 rows the draft gave a reason |
|---|---|---|---|
| reason code | 98.0% | 0.95 | 93.9% (kappa 0.92) |
| from vendor | 97.3% | 0.85 | 87.9% |
| to vendor | 97.3% | 0.85 | 87.9% |
| direction | 98.7% | 0.95 | 93.9% |

seed_v1 gave 94.7% (kappa 0.85) on the reason code, so the second pass changed less this time. Three reason codes
changed: 6901 (performance to none: it describes which workloads vendors target) and 7052 (cost to none: a storage
design trade-off) lost their reason, and 1272 gained one (none to performance: "But at the larger org, we started
having performance issues." comes just before the Redshift-to-Snowflake move; the evidence sentence was changed to
that verbatim sentence). The four vendor changes (413, 453, 454, 10833) fill in a from-vendor where a post compares
Databricks or Snowflake with a non-vendor tool such as DuckDB.

The reviewer's notes flag five documents as vendor or self-promotional content (164, 453, 454, 6565, 10626) and
suggest a 'promotional' flag. That flag is not implemented; the documents keep their labels.

Agreement this high between two model passes should not be read as accuracy (see the limitation above): the
reviewer saw the draft and excerpts only, which makes it easy to agree.

### Detectors scored on seed_v2

`python -m analysis.labeling.detector_eval --sample seed_v2` (`detector_eval_seed_v2.csv`), positives = 36
documents with a reason or a move in the `claude_review` labels:

| detector | flagged | true positives | precision | recall |
|---|---|---|---|---|
| v1 phrase list | 47 | 12 | 25.5% | 33.3% |
| v2 platform + move/reason sentence | 120 | 35 | 29.2% | 97.2% |

seed_v2 was drawn with 120 of 150 documents flagged by v2, so its recall here is inflated by design: only the 30
unflagged documents can hold a miss (one, 6538, does). The fair reading is precision, which holds at about 30% on a
sample the detector was not tuned on (32% on seed_v1). v1's recall falls from 82% on seed_v1 to 33% here because
this sample was not drawn on v1's phrases.

## Freeze and export (2026-09-28)

Data collection and labelling are frozen. `python -m analysis.export.findings` (Actions `phase2`, step
`export_findings`) writes `analysis/export/findings.json` from the database and the committed audit files, and stops
if the database `claude_review` labels differ from the committed label files. Every quote in it is re-checked as
verbatim against its stored document. The brief is [findings.md](findings.md); the file's schema is
[data_contract.md](data_contract.md).

**Promotional sensitivity** (no pipeline flag; labels unchanged). The seed_v2 review notes flag 5 documents as vendor
or self-promotional (164, 453, 454, 6565, 10626), all with a reason. Without them there are 58 reasons: cost 20 to
17, performance 8 to 6, nothing else changes, and cost stays first. The seed_v1 review notes flag 3 more (1121,
1400, 11070); without all 8 there are 55 reasons and cost is 15, still first.

