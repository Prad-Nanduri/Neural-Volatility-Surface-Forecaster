"""Evaluation entry point.

Currently supports only ``--smoke-test``: builds a surface from the
deterministic demo fixture and prints diagnostics. Model benchmarks land in
the neural-calibration session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from quant.surface import RawQuote, assemble_surface  # noqa: E402


def smoke_test() -> int:
    fixture = REPO_ROOT / "tests" / "fixtures" / "btc_chain_demo.json"
    data = json.loads(fixture.read_text())
    quotes = [
        RawQuote(
            strike=q["strike"],
            expiry_years=q["expiry_years"],
            option_type=q["option_type"],
            bid=q["bid"],
            ask=q["ask"],
            spot=data["spot"],
            rate=data["rate"],
            dividend_yield=data.get("dividend_yield", 0.0),
        )
        for q in data["quotes"]
    ]
    result = assemble_surface(quotes)
    print(
        json.dumps(
            {
                "accepted": result.n_accepted,
                "rejected": len(result.rejected),
                "max_residual": result.max_residual,
                "diagnostics": result.diagnostics,
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test()
    parser.error("only --smoke-test is supported for now")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
