"""Print what is in the database: documents, mentions and signals, each counted on its own.

Used at the end of every ingestion run (including in GitHub Actions) so the three
numbers that decide whether the corpus is thick enough are visible in the log.
Signals are reported separately from documents and never added to them.
"""

from __future__ import annotations

from sqlalchemy import text

from ingestion.load_to_db import get_engine

QUERIES = {
    "Documents by source": """
        SELECT s.name AS source, COUNT(d.id) AS documents,
               MIN(d.posted_at)::date AS earliest, MAX(d.posted_at)::date AS latest, MAX(s.last_run_at) AS last_run
        FROM sources s LEFT JOIN documents d ON d.source_id = s.id GROUP BY s.name ORDER BY s.name""",
    "Documents mentioning each entity (tech: rows are technologies, not vendors)": """
        SELECT vendor AS entity, COUNT(DISTINCT document_id) AS documents, SUM(mention_count) AS mentions
        FROM mentions GROUP BY vendor ORDER BY documents DESC""",
    "Signals by type (separate from documents)": """
        SELECT signal_type, COUNT(DISTINCT entity) AS entities, COUNT(*) AS rows,
               MIN(period_start) AS first_period, MAX(period_start) AS last_period
        FROM signals GROUP BY signal_type ORDER BY signal_type""",
}


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        totals = conn.execute(text(
            "SELECT (SELECT COUNT(*) FROM documents), (SELECT COUNT(*) FROM mentions), (SELECT COUNT(*) FROM signals)"
        )).one()
        print("=" * 72)
        print(f"TOTALS  documents={totals[0]}  mention_rows={totals[1]}  signal_rows={totals[2]}")
        print("=" * 72)
        for title, sql in QUERIES.items():
            rows = conn.execute(text(sql)).all()
            print(f"\n{title}:")
            if not rows:
                print("  (none)")
                continue
            cols = list(rows[0]._fields)
            widths = [max(len(c), *(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
            print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
            for r in rows:
                print("  " + "  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


if __name__ == "__main__":
    main()
