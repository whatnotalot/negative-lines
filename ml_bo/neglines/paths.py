import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"


def _gold_path() -> Path:
    """NEGLINES_GOLD if set, else the team repo's shared gold set, else a local copy under data/raw/."""
    candidates = [Path(p) for p in [os.environ.get("NEGLINES_GOLD")] if p]
    candidates += [ROOT.parent / "data" / "Negative_Lines_Reconciled_Gold_Set.xlsx",
                   DATA_RAW / "Negative_Lines_Machine_Reconciled_Gold_Set.xlsx"]
    return next((p for p in candidates if p.exists()), candidates[0])


GOLD_XLSX = _gold_path()
