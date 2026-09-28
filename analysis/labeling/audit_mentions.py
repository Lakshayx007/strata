"""List every document where an entity's term appears but the matcher does not count the entity.

    python -m analysis.labeling.audit_mentions --entity snowflake

For a disambiguation rule this is the full set of documents it removed relative to counting every
occurrence, with the matcher's reason and snippet (public post text, no author data), so each removal can be
checked by hand. Writes data/processed/labeling/audit_<entity>.csv.
"""

from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy import text

from analysis.labeling.sample import EXPORT_DIR
from ingestion.normalize import find_mentions_with_rejections


def main() -> None:
    from ingestion.load_to_db import get_engine

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entity", default="snowflake")
    args = ap.parse_args()
    with get_engine().connect() as conn:
        rows = conn.execute(text("""SELECT d.id, s.name, d.title, d.body FROM documents d JOIN sources s ON s.id = d.source_id
                                    WHERE (d.body ILIKE :p OR d.title ILIKE :p)
                                      AND NOT EXISTS (SELECT 1 FROM mentions m WHERE m.document_id = d.id AND m.vendor = :e)
                                    ORDER BY s.name, d.id"""), {"p": f"%{args.entity}%", "e": args.entity}).all()
    out = []
    for i, source, title, body in rows:
        rej = [r for r in find_mentions_with_rejections(body or "", title)[1] if r.entity == args.entity]
        for r in rej[:2]:
            out.append({"document_id": i, "source": source, "reason": r.reason, "snippet": r.snippet[:170]})
        if not rej:
            out.append({"document_id": i, "source": source, "reason": "substring_only", "snippet": ""})
    df = pd.DataFrame(out)
    print(f"{df.document_id.nunique() if len(df) else 0} documents contain '{args.entity}' but do not count it\n")
    if len(df):
        print(df.groupby(["source", "reason"]).document_id.nunique().to_string(), "\n")
        for r in df[df.reason != "substring_only"].itertuples():
            print(f"  {r.document_id} {r.source[:2]} [{r.reason}] {r.snippet}")
        df.to_csv(EXPORT_DIR / f"audit_{args.entity}.csv", index=False)


if __name__ == "__main__":
    main()
