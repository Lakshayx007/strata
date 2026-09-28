# Strata findings: what drives data-platform choices in developer discussion

*Frozen 2026-09-28. Data collection and labelling are closed. Every figure below is in
[`analysis/export/findings.json`](../analysis/export/findings.json), which is generated from the database by
`python -m analysis.export.findings`, or in the audit files it names. How each number was produced is in
[methodology.md](methodology.md). No label in this project was reviewed by a human (see Limitations).*

## Headline: cost is the most common stated reason, and "you don't need this much platform" is a close cousin

In 300 labelled discussion documents (Hacker News 120, Stack Exchange 90, Dev.to 90), **63 give a reason for a
data-platform choice**:

| Reason | Count | Share of 63 |
|---|---|---|
| Cost | 20 | 32% |
| Operational simplicity | 11 | 17% |
| Lock-in and openness | 8 | 13% |
| Performance and scale | 8 | 13% |
| Right-sizing (a smaller tool is enough) | 7 | 11% |
| Ecosystem fit | 4 | 6% |
| Other | 3 | 5% |
| Governance and security | 2 | 3% |

Cost and right-sizing together are 27 of 63: over two in five stated reasons are about paying for more platform
than the workload needs. With only 63 reasons, the categories from lock-in down are too close to rank against each
other; the gap between cost (20) and the next category (11) is the one ordering the data supports.

**Promotional check:** dropping the 5 documents the seed_v2 review flagged as vendor or self-promotional leaves 58
reasons (cost 17, operational simplicity 11, lock-in 8, right-sizing 7, performance 6), so cost stays first; dropping
all 8 flagged across both reviews leaves 55 with cost at 15, still first.

## Share of voice (12,056 discussion documents; 5,941 name a vendor)

| Vendor | Documents | Share of vendor-naming documents | Switching-language documents |
|---|---|---|---|
| Snowflake | 1,812 | 30.5% | 326 |
| Databricks | 1,687 | 28.4% | 245 |
| Google | 1,376 | 23.2% | 168 |
| AWS | 1,166 | 19.6% | 150 |
| Microsoft | 687 | 11.6% | 66 |
| Cloudera | 55 | 0.9% | 7 |

Counts use the corrected Snowflake matcher (idioms such as "special snowflake" and snowflake IDs no longer count).
A document can name several vendors, so shares add up to more than 100%. **Dev.to caveat:** the Dev.to feeds
include tags for Databricks, Snowflake, BigQuery and Redshift but none for Cloudera, so Cloudera's 3 Dev.to
documents understate it there. On Hacker News and Stack Exchange, where every vendor had the same search budget,
Cloudera still has 30 and 19 documents against 722 to 857 Hacker News documents for each of Snowflake, Databricks
and Google.

## Cloudera: nearly absent, and what is there is maintenance and exit

- **55 documents** (Hacker News 30, Stack Exchange 19, Dev.to 3, GitHub 3); 24 were labelled. None describes
  adopting Cloudera. One describes leaving it. The 9 labelled Stack Exchange documents are all questions about
  running existing Hadoop-era clusters (Hue, MapReduce, YARN, HDFS, the quickstart image).
- **Stranded on the free edition ([7279](https://stackoverflow.com/questions/77139887/cloudera-enterprise-community-edition-for-rhel-8),
  Stack Overflow, 2023-09-20).** "We are running a mini DWH platform with Cloudera Enterprise community version."
  The team must move to RHEL 8 and is "not able to find any upgraded version of Cloudera Enterprise which supports
  RHEL 8". "We want to stay on Community edition of Cloudera."
- **Exit to open source ([220](https://news.ycombinator.com/item?id=43984709), Hacker News, 2025-05-14).** "I know a
  company who had 2PBs+ of data in Cloudera. But instead of moving to the cloud (and Databricks), they saved 5X
  costs by building their own analytics platform with Iceberg, Trino and Superset." This is second-hand.
- **What it suggests:** in public developer discussion, Cloudera appears as an installed base being maintained or
  left, not as a platform being chosen; its users' exits go to open-source stacks as well as to cloud vendors.
- **What it can't prove:** the sources lean cloud-native, and on-premises estates are discussed less in public, so
  low share of voice is not low market share. Two cases are anecdotes, one of them second-hand. Nothing here says
  anything about Cloudera's licensing or support policy.

## In their words

- Cost: "We switched to Snowflake, saved money, got better performance, and had a simpler setup."
  ([1611](https://news.ycombinator.com/item?id=48084671), HN, AWS Redshift to Snowflake)
- Cost: "The quickest way to 10x your costs is to move a Vertica workload to Snowflake (last I heard my old job is
  now up to 40x)." ([274](https://news.ycombinator.com/item?id=44884657), HN)
- Operational simplicity: "Trying to just run a simple Spark query using an S3 Table Bucket was enough to remind me
  why Snowflake and Databricks are printing money by making it a more user friendly experience."
  ([649](https://news.ycombinator.com/item?id=48086968), HN)
- Lock-in: "Snowflake's optimizations lived inside a proprietary storage layout nothing else could read."
  ([11002](https://dev.to/aiexplore369zoho/databricks-vs-snowflake-27-lakehouse-vs-warehouse-the-architecture-bet-each-company-made-2m8l), Dev.to)
- Performance: "But at the larger org, we started having performance issues. We migrated from Redshift to
  Snowflake" ([1272](https://news.ycombinator.com/item?id=44045610), HN)
- Right-sizing: "In fact, I just advised someone recently to simply use Postgres instead of BigQuery since they had
  <1TB and their queries weren't super intensive." ([1268](https://news.ycombinator.com/item?id=43966737), HN)
- Governance: "The best thing I've built in a long time is replacing a complex (and scary) permissions system built
  on top of Snowflake with single role duckdb databases" ([1750](https://news.ycombinator.com/item?id=48600360), HN)
- Ecosystem fit: "Fabric wins on Microsoft-shop fit because the identity, licensing, and Power BI story compound"
  ([10963](https://dev.to/gowthampotureddi/microsoft-fabric-onelake-deep-dive-for-data-engineers-lakehouse-warehouse-real-time-in-one-4fi0), Dev.to)

## What I'd do next as a PM

- **Get a human-validated number before anyone quotes a ranking.** Two people independently label a stratified
  100-document subset; if cost still leads at human-level agreement, the headline stands.
- **Treat cost and right-sizing as one pricing question.** 27 of 63 reasons are about paying for more than the
  workload needs, and the right-sizing reasons point mostly to Postgres or DuckDB rather than a rival warehouse. The
  question to test with customers is how small workloads get a bill that feels proportionate.
- **Don't size Cloudera from this corpus.** Public developer channels barely see on-premises estates. Customer
  interviews with teams on legacy Hadoop, starting with the forced-upgrade moment in 7279, would say whether
  "stranded" and "exiting to open source" are a pattern or two anecdotes.

## Limitations

- **No human review.** Every label is a model draft plus a second-model review of excerpts. There is no ground truth.
- **Agreement is model-vs-model:** 94.7% on reason code for seed_v1 (kappa 0.85) and 98.0% for seed_v2 (kappa 0.95).
  It measures consistency between two similar passes, not accuracy.
- **Small n.** 63 reasons in 300 documents; categories below about 10 cannot be ranked against each other.
- **Source bias.** Stack Exchange gives almost no reasons (1 of 90 labelled documents; Hacker News 40 of 120, Dev.to
  22 of 90), so the reason mix is mostly Hacker News and Dev.to voices. Reddit, G2, Gartner Peer Insights and
  TrustRadius are not in the corpus. Samples over-draw documents with switching language, so the counts describe
  labelled documents, not the whole corpus.
- **Proposed "deployment control" category was not added:** of 27 corpus documents matching it strictly, 3 were
  real cases on a full read.
