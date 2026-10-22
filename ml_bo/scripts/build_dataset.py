"""Export the normalized gold set, compliance screen and campaign tables as CSV for the team.

Writes data/processed/*.csv and data/processed/issues.json.
Usage: python scripts/build_dataset.py
"""
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from neglines.campaigns import all_campaigns  # noqa: E402
from neglines.compliance import flag_table, screen_records  # noqa: E402
from neglines.data import load_gold  # noqa: E402
from neglines.paths import DATA_PROCESSED  # noqa: E402


def main():
    g = load_gold()
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    g.records.to_csv(DATA_PROCESSED / "records.csv", index=False)
    g.components.to_csv(DATA_PROCESSED / "components.csv", index=False)
    g.results.to_csv(DATA_PROCESSED / "results.csv", index=False)
    screen_records(g.components, g.records).to_csv(DATA_PROCESSED / "record_compliance.csv")
    flag_table(g.components, g.records).to_csv(DATA_PROCESSED / "component_flags.csv", index=False)
    for key, c in all_campaigns().items():
        c.table.to_csv(DATA_PROCESSED / f"campaign_{key}.csv", index=False)
    (DATA_PROCESSED / "issues.json").write_text(json.dumps(g.issues, indent=2, ensure_ascii=False), encoding="utf-8")
    for p in sorted(DATA_PROCESSED.iterdir()):
        print(f"{p.name:<28} {p.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
