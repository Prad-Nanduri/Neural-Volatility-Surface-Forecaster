"""Offline Heston-surrogate dataset generation (spec section 7).

Delegates to ml/heston_pipeline.py. Example:
    python ml/generate_dataset.py --n 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from heston_pipeline import generate_dataset  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="ml/data/heston_surrogate.npz")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--outputs", type=int, default=84)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate_dataset(args.path, n=args.n, outputs=args.outputs, seed=args.seed)
    print(f"dataset written to {args.path}")
