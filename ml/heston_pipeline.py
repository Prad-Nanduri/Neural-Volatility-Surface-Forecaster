"""Reproducible Heston-surrogate dataset, training, and evaluation utilities."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import minimize
from torch import nn
from torch.nn import functional as F


def unconstrained_to_heston(x: torch.Tensor) -> torch.Tensor:
    kappa = F.softplus(x[..., 0]) + 1e-4
    theta = F.softplus(x[..., 1]) + 1e-5
    sigma_v = F.softplus(x[..., 2]) + 1e-4
    rho = torch.tanh(x[..., 3]).clamp(-0.999, 0.999)
    v0 = F.softplus(x[..., 4]) + 1e-5
    return torch.stack([kappa, theta, sigma_v, rho, v0], dim=-1)


class HestonSurfaceSurrogate(nn.Module):
    def __init__(self, n_outputs: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 256),
            nn.SiLU(),
            nn.Linear(256, 256),
            nn.SiLU(),
            nn.Linear(256, 256),
            nn.SiLU(),
            nn.Linear(256, n_outputs),
        )

    def forward(self, params: torch.Tensor) -> torch.Tensor:
        return self.net(params)


def calibrate_surrogate(observed, model, x0, device="cpu"):
    observed_t = torch.as_tensor(observed, dtype=torch.float32, device=device)
    model.eval()

    def objective(x):
        x_t = torch.tensor(x, dtype=torch.float32, device=device, requires_grad=True)
        pred = model(unconstrained_to_heston(x_t)).reshape_as(observed_t)
        loss = ((pred - observed_t) ** 2).mean()
        loss.backward()
        return float(loss.detach()), x_t.grad.detach().cpu().numpy().astype(np.float64)

    result = minimize(
        objective,
        np.asarray(x0, dtype=np.float64),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 150, "ftol": 1e-10},
    )
    params = unconstrained_to_heston(
        torch.tensor(result.x, dtype=torch.float32, device=device)
    )
    return result, params.detach().cpu().numpy()


def generate_dataset(path="ml/data/heston_surrogate.npz", n=10000, outputs=84, seed=42):
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(n, 5)).astype(np.float32)
    params = unconstrained_to_heston(torch.from_numpy(raw)).numpy()
    # Replace this deterministic proxy with the validated Heston pricer from src/quant.
    k = np.linspace(-0.8, 0.8, outputs, dtype=np.float32)
    surfaces = (
        params[:, 1:2]
        + params[:, 4:5]
        + 0.15 * params[:, 3:4] * k[None, :]
        + 0.03 * params[:, 2:3] * k[None, :] ** 2
    ).astype(np.float32)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, params=params, surfaces=surfaces, raw=raw, seed=seed)


def train(
    path="ml/data/heston_surrogate.npz",
    output="ml/artifacts/heston_surrogate.pt",
    epochs=50,
    batch_size=256,
):
    data = np.load(path)
    x = torch.from_numpy(data["params"])
    y = torch.from_numpy(data["surfaces"])
    model = HestonSurfaceSurrogate(y.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3)
    for _ in range(epochs):
        order = torch.randperm(len(x))
        for ids in order.split(batch_size):
            loss = F.smooth_l1_loss(model(x[ids]), y[ids])
            opt.zero_grad()
            loss.backward()
            opt.step()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "n_outputs": y.shape[1]}, output)
    return model


def evaluate(path="ml/data/heston_surrogate.npz", checkpoint=None, smoke_test=False):
    data = np.load(path)
    model = HestonSurfaceSurrogate(data["surfaces"].shape[1])
    if checkpoint:
        model.load_state_dict(torch.load(checkpoint, map_location="cpu")["state_dict"])
    with torch.no_grad():
        pred = model(torch.from_numpy(data["params"])).numpy()
    rmse = float(np.sqrt(np.mean((pred - data["surfaces"]) ** 2)))
    if smoke_test and not np.isfinite(rmse):
        raise RuntimeError("non-finite evaluation metric")
    return {"rmse": rmse, "samples": int(len(pred))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "train", "evaluate"])
    parser.add_argument("--path", default="ml/data/heston_surrogate.npz")
    parser.add_argument("--output", default="ml/artifacts/heston_surrogate.pt")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.command == "generate":
        generate_dataset(args.path)
    elif args.command == "train":
        train(args.path, args.output)
    else:
        print(
            evaluate(
                args.path,
                args.output if Path(args.output).exists() else None,
                args.smoke_test,
            )
        )
