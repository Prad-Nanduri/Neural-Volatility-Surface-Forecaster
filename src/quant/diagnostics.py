import numpy as np


def arbitrage_diagnostics(call_prices, total_variance, tol=1e-6):
    butterfly = np.diff(call_prices, n=2, axis=1)
    calendar = np.diff(total_variance, axis=0)
    return {
        "butterfly_violation_rate": float(np.mean(butterfly < -tol)),
        "calendar_violation_rate": float(np.mean(calendar < -tol)),
        "worst_butterfly": float(np.min(butterfly)),
        "worst_calendar": float(np.min(calendar)),
    }
