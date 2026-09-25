# Strata methodology (Phase 1: collection)

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
- Reddit uses app-only, read-only OAuth, which means no user account. GitHub uses a classic token with no scopes.
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
Every dropped document is written to `data/processed/dedupe_report_*.csv` with the document it duplicated and the
similarity score.

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
