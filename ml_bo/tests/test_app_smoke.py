"""Render every page headlessly through the real navigation and report exceptions.
Run: python tests/test_app_smoke.py"""
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path[:0] = [str(ROOT), str(APP)]
warnings.filterwarnings("ignore")

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["home", "demo", "atlas", "gaps", "rls", "surrogate", "replay", "agent", "design", "byod", "anions"]


def seg(i, value):
    return lambda at: at.segmented_control[i].set_value(value).run()


def click(label):
    return lambda at: next(b for b in at.button if b.label == label).click().run()


def toggle(i):
    return lambda at: at.toggle[i].set_value(True).run()


EXTRA = [("design", "ebeam", seg(0, "ebeam")), ("design", "su8", seg(0, "su8")),
         ("surrogate", "euv", seg(0, "euv")), ("replay", "ebeam", seg(0, "ebeam")), ("gaps", "su8", seg(0, "su8")),
         ("demo", "flag III-1", toggle(0)), ("agent", "run planner", click("Run agent"))]


def run(page, action=None):
    at = AppTest.from_file(str(APP / "streamlit_app.py"), default_timeout=900)
    at.run()
    if page != "home":
        at.switch_page(f"views/{page}.py").run()
    if action is not None and not at.exception:
        action(at)
    return at, [e.value for e in at.exception]


def main():
    failures = 0
    for spec in [(p, "", None) for p in PAGES] + EXTRA:
        t0 = time.time()
        at, errs = run(spec[0], spec[2])
        failures += bool(errs)
        print(f"{'ok' if not errs else 'FAIL':4} {spec[0]:<10} {spec[1]:<12} {time.time() - t0:5.1f}s", *errs[:1], flush=True)
        if spec[1] == "run planner" and not errs:
            brief = [m.value for m in at.markdown if "## Goal" in m.value]
            print("     brief rendered:", bool(brief))
            failures += not brief
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
