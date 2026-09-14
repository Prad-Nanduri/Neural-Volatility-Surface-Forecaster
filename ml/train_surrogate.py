"""Train the Heston surface surrogate (spec section 7).

Delegates to ml/heston_pipeline.py. Example:
    python ml/train_surrogate.py --epochs 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from heston_pipeline import train  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="ml/data/heston_surrogate.npz")
    parser.add_argument("--output", default="ml/artifacts/heston_surrogate.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()
    train(args.path, args.output, epochs=args.epochs, batch_size=args.batch_size)
    print(f"checkpoint written to {args.output}")
