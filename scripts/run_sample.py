"""Run the full agentic pipeline from the command line on the bundled sample proposals.

Usage:
    python scripts/run_sample.py                                   # offline heuristic (no key)
    GEMINI_API_KEY=... python scripts/run_sample.py --provider "Google Gemini (free tier)"
Writes the complete run JSON to sample_output/sample_run.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import db  # noqa: E402
from core.evaluation_agent import PROVIDER_PRESETS, LLMConfig  # noqa: E402
from core.orchestrator import Orchestrator, SupplierInput  # noqa: E402
from core.samples import SAMPLE_DIR, SAMPLE_SUPPLIERS  # noqa: E402


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="Offline heuristic (no API key - demo only)", choices=list(PROVIDER_PRESETS))
    p.add_argument("--model", default=None)
    p.add_argument("--out", default=os.path.join(ROOT, "sample_output", "sample_run.json"))
    args = p.parse_args()

    preset = PROVIDER_PRESETS[args.provider]
    key = os.environ.get(preset["secret"], "") if preset["secret"] else ""
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if preset["secret"] and not key and os.path.exists(secrets_path):  # same key the app uses
        import tomllib
        with open(secrets_path, "rb") as fh:
            key = tomllib.load(fh).get(preset["secret"], "")
    cfg = LLMConfig(provider=args.provider, kind=preset["kind"], model=args.model or preset["model"],
                    api_key=key, base_url=preset["base_url"])
    db.init_db()
    suppliers = []
    for name, d, exp, fn in SAMPLE_SUPPLIERS:
        with open(os.path.join(SAMPLE_DIR, fn), "rb") as f:
            suppliers.append(SupplierInput(name, d, exp, fn, f.read()))

    result = Orchestrator(cfg, on_step=lambda s, d: print(f"[{s}] {d}")).run(suppliers)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nRun {result['rfp_run_id']} - {result['status']}")
    print(f"{'Rank':<5}{'Supplier':<18}{'Absolute':>10}{'PPI':>9}")
    for s in result["suppliers"]:
        print(f"{s['final_rank']:<5}{s['supplier_name']:<18}{s['absolute_score']:>10.2f}{s['ppi']:>9.2f}")
    print(f"\nSaved {args.out}")
