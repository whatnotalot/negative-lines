"""Exercise the design agent offline: a scripted stand-in for the Claude client drives the real tool loop,
and the rule-based planner runs on three goals. Run: python tests/test_agent.py"""
import json
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

from neglines.agent import Toolbox, run_agent, run_planner  # noqa: E402


def tool_use(i, name, **inp):
    return NS(type="tool_use", id=f"toolu_{i}", name=name, input=inp)


class ScriptedClient:
    """Returns pre-written responses and records every request, standing in for anthropic.Anthropic()."""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(json.loads(json.dumps(kw, default=lambda o: o.__dict__)))
        return self.script.pop(0)


usage = NS(input_tokens=100, output_tokens=50)
script = [
    NS(stop_reason="tool_use", usage=usage, content=[
        NS(type="thinking", thinking="Check the campaigns and surrogate skill first."),
        tool_use(1, "list_campaigns"), tool_use(2, "surrogate_skill", campaign="ebeam")]),
    NS(stop_reason="tool_use", usage=usage, content=[
        tool_use(3, "propose_batch", campaign="ebeam", mode="mo", batch_size=2, compliance_policy="exclude",
                 swap_fluorosurfactant=True),
        tool_use(4, "propose_batch", campaign="ebeam")]),           # invalid: missing arguments
    NS(stop_reason="end_turn", usage=usage, content=[NS(type="text", text="## Goal\nPFAS-reduced e-beam resist.")]),
]


def main():
    client = ScriptedClient(script)
    run = run_agent("Design a PFAS-reduced e-beam resist", Toolbox(), client=client)
    calls = [e.content["name"] for e in run.tool_calls()]
    results = [e.content for e in run.events if e.kind == "tool_result"]
    assert calls == ["list_campaigns", "surrogate_skill", "propose_batch", "propose_batch"], calls
    assert "error" in results[3] and "missing" in results[3]["error"], results[3]
    props = results[2]["output"]["proposals"]
    assert props and all(not any(f["rule"] == "OECD_PFAS" for f in p["compliance"]) for p in props)
    # tool results go back in one user message, ids matched, errors flagged
    last = client.requests[-1]["messages"][-1]
    assert last["role"] == "user" and [c["tool_use_id"] for c in last["content"]] == ["toolu_3", "toolu_4"]
    assert last["content"][1]["is_error"] is True
    assert client.requests[0]["model"] == "claude-opus-5-5" and client.requests[0]["fallbacks"] == "default"
    assert run.final.startswith("## Goal") and run.usage["output_tokens"] == 150
    print("agent loop: ok", calls)
    print("  top proposal:", json.dumps(props[0]["formulation"]), json.dumps(props[0]["predicted"])[:200])

    for goal in ["Design a PFAS-free e-beam resist with low LER",
                 "Find a PFAS-free EUV formulation with LWR under 3.3 nm",
                 "Reduce via cracking in thick SU-8 films"]:
        r = run_planner(goal)
        print(f"\nplanner: {goal}\n  tools: {[e.content['name'] for e in r.tool_calls()]}")
        print("  " + r.final.replace("\n", "\n  ")[:1400])


if __name__ == "__main__":
    main()
