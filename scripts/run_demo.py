"""Run the whole pipeline on the NovaCart demo data from the terminal (no UI) and print a summary.

    python scripts/run_demo.py            # uses the configured database (default: data/blindspot.db)
    EMBEDDING_BACKEND=tfidf python scripts/run_demo.py     # fully offline"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services import analysis, companies, datasets  # noqa: E402
from backend.services.companies import Conflict  # noqa: E402
from database.connection import init_db  # noqa: E402


def main() -> int:
    init_db()
    try:
        company = companies.create_company("NovaCart (demo)", "E-commerce", "Synthetic demo company")
    except Conflict:
        company = next(c for c in companies.list_companies() if c["name"] == "NovaCart (demo)")
    print(datasets.load_sample(company["id"])["message"])
    sid = analysis.start_analysis(company["id"], background=False)
    status = analysis.session_status(sid)
    if status["status"] != "completed":
        print("Analysis failed:", status["error"])
        return 1
    bundle = analysis.get_bundle(sid)
    ov = bundle["overview"]
    print(f"\nAnalysis #{sid} for '{company['name']}'  (embeddings: {bundle['meta']['embedding_backend']}, topics: {bundle['meta']['topic_backend']})")
    print(f"  conversations {ov['total_conversations']} | topics {ov['total_topics']} | potential blind spots {ov['total_blind_spots']} | "
          f"emerging issues {ov['total_emerging_issues']} | sentiment {ov['overall_sentiment']:+.2f} | avg score {ov['avg_blind_spot_score']:.1f}")
    print("\nRanked blind spots")
    for b in bundle["blind_spots"]:
        print(f"  #{b['rank']} {b['topic_label'][:34]:34s} score {b['score']:5.1f} {b['severity']:11s} "
              f"importance {b['importance']:4.0f} coverage {b['coverage_norm']:4.0f} gap {b['gap']:4.0f}  [{b['classification']}]")
    print("\nTop recommendations")
    for r in bundle["recommendations"][:5]:
        print(f"  [{r['priority']}] {r['category']:16s} {r['topic_label']}: {r['suggested_action'][:110]}")
    print("\nOpen the dashboard to explore:  streamlit run frontend/app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
