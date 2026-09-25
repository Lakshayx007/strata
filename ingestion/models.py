"""The common envelope every adapter returns.

Adapters stay thin: they wrap each API object untouched in `raw` and let
normalize.py do the mapping. Keeping the native payload means we can re-derive
documents later without re-fetching, and the raw JSONL is the audit trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class FetchedItem:
    source: str  # key into config.SOURCE_REGISTRY
    kind: str  # e.g. submission, comment, story, question, tag_count, repo_metric, doc_page
    external_id: str
    fetched_at: datetime
    query: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["fetched_at"] = self.fetched_at.isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "FetchedItem":
        return cls(**{**d, "fetched_at": datetime.fromisoformat(d["fetched_at"])})


# Kinds that are time-series signals rather than text documents. They never
# enter `documents`; normalize.py writes them to data/processed instead.
METRIC_KINDS = {"tag_count", "repo_stars", "repo_contributors", "repo_issue"}
