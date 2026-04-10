from __future__ import annotations

import random

from .contracts import SystemStack


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _noise(rng: random.Random, scale: float = 0.02) -> float:
    return (rng.random() - 0.5) * 2 * scale


def _stack_flags(stack: SystemStack) -> tuple[float, float, float, float, float]:
    return (
        1.0 if stack.private_state else 0.0,
        1.0 if stack.shared_traces else 0.0,
        1.0 if stack.heredity else 0.0,
        1.0 if stack.selection_pressure else 0.0,
        1.0 if stack.heterogeneity_governance else 0.0,
    )


def run_static_baseline(seed: int, stack: SystemStack) -> dict[str, float]:
    rng = random.Random(seed)
    private_state, shared_traces, heredity, selection_pressure, governance = _stack_flags(stack)
    post_shift_survival = _clamp(
        0.80
        + 0.03 * private_state
        + 0.03 * shared_traces
        + 0.02 * heredity
        + 0.01 * selection_pressure
        + 0.01 * governance
        + _noise(rng, 0.01),
        0.0,
        1.0,
    )
    return {
        "adaptation_lag": round(0.8 + _noise(rng, 0.1), 4),
        "post_shift_survival": round(post_shift_survival, 4),
        "recovery_slope": round(_clamp(0.22 + 0.02 * heredity + _noise(rng, 0.01), 0.0, 1.0), 4),
        "memory_leverage": round(_clamp(0.02 + 0.04 * shared_traces + _noise(rng, 0.01), 0.0, 1.0), 4),
        "organization_advantage": round(_clamp(0.04 + 0.03 * selection_pressure + _noise(rng, 0.01), 0.0, 1.0), 4),
        "heterogeneity_absorption": round(_clamp(0.06 + 0.04 * governance + _noise(rng, 0.01), 0.0, 1.0), 4),
    }


def run_regime_shift(seed: int, stack: SystemStack) -> dict[str, float]:
    rng = random.Random(seed)
    private_state, shared_traces, heredity, selection_pressure, governance = _stack_flags(stack)
    adaptation_lag = max(
        0.0,
        9.6
        - 0.9 * private_state
        - 2.4 * shared_traces
        - 1.8 * heredity
        - 2.9 * selection_pressure
        - 0.8 * governance
        + _noise(rng, 0.25),
    )
    post_shift_survival = _clamp(
        0.18
        + 0.05 * private_state
        + 0.18 * shared_traces
        + 0.13 * heredity
        + 0.18 * selection_pressure
        + 0.05 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    recovery_slope = _clamp(
        0.05
        + 0.03 * private_state
        + 0.08 * shared_traces
        + 0.12 * heredity
        + 0.15 * selection_pressure
        + 0.04 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    memory_leverage = _clamp(
        0.02
        + 0.28 * shared_traces
        + 0.08 * heredity
        + 0.03 * selection_pressure
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    organization_advantage = _clamp(
        0.03
        + 0.05 * shared_traces
        + 0.08 * heredity
        + 0.18 * selection_pressure
        + 0.08 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    heterogeneity_absorption = _clamp(
        0.02
        + 0.03 * private_state
        + 0.06 * shared_traces
        + 0.08 * heredity
        + 0.20 * selection_pressure
        + 0.12 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    return {
        "adaptation_lag": round(adaptation_lag, 4),
        "post_shift_survival": round(post_shift_survival, 4),
        "recovery_slope": round(recovery_slope, 4),
        "memory_leverage": round(memory_leverage, 4),
        "organization_advantage": round(organization_advantage, 4),
        "heterogeneity_absorption": round(heterogeneity_absorption, 4),
    }


def run_heterogeneous_brains(seed: int, stack: SystemStack) -> dict[str, float]:
    rng = random.Random(seed)
    private_state, shared_traces, heredity, selection_pressure, governance = _stack_flags(stack)
    adaptation_lag = max(
        0.0,
        10.8
        - 0.6 * private_state
        - 1.1 * shared_traces
        - 1.4 * heredity
        - 3.1 * selection_pressure
        - 1.6 * governance
        + _noise(rng, 0.25),
    )
    post_shift_survival = _clamp(
        0.22
        + 0.03 * private_state
        + 0.08 * shared_traces
        + 0.08 * heredity
        + 0.17 * selection_pressure
        + 0.08 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    recovery_slope = _clamp(
        0.04
        + 0.03 * private_state
        + 0.04 * shared_traces
        + 0.06 * heredity
        + 0.14 * selection_pressure
        + 0.08 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    memory_leverage = _clamp(
        0.01
        + 0.16 * shared_traces
        + 0.05 * heredity
        + 0.04 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    organization_advantage = _clamp(
        0.04
        + 0.03 * shared_traces
        + 0.07 * heredity
        + 0.24 * selection_pressure
        + 0.12 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    heterogeneity_absorption = _clamp(
        0.05
        + 0.03 * private_state
        + 0.08 * shared_traces
        + 0.10 * heredity
        + 0.32 * selection_pressure
        + 0.18 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    return {
        "adaptation_lag": round(adaptation_lag, 4),
        "post_shift_survival": round(post_shift_survival, 4),
        "recovery_slope": round(recovery_slope, 4),
        "memory_leverage": round(memory_leverage, 4),
        "organization_advantage": round(organization_advantage, 4),
        "heterogeneity_absorption": round(heterogeneity_absorption, 4),
    }


def run_memory_timescale_split(seed: int, stack: SystemStack) -> dict[str, float]:
    rng = random.Random(seed)
    private_state, shared_traces, heredity, selection_pressure, governance = _stack_flags(stack)
    adaptation_lag = max(
        0.0,
        8.4
        - 1.2 * private_state
        - 2.2 * shared_traces
        - 2.0 * heredity
        - 1.2 * selection_pressure
        - 0.4 * governance
        + _noise(rng, 0.25),
    )
    post_shift_survival = _clamp(
        0.20
        + 0.10 * private_state
        + 0.17 * shared_traces
        + 0.14 * heredity
        + 0.06 * selection_pressure
        + 0.03 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    recovery_slope = _clamp(
        0.03
        + 0.05 * private_state
        + 0.09 * shared_traces
        + 0.18 * heredity
        + 0.07 * selection_pressure
        + 0.03 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    memory_leverage = _clamp(
        0.02
        + 0.08 * private_state
        + 0.34 * shared_traces
        + 0.12 * heredity
        + 0.02 * selection_pressure
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    organization_advantage = _clamp(
        0.02
        + 0.05 * shared_traces
        + 0.09 * heredity
        + 0.08 * selection_pressure
        + 0.04 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    heterogeneity_absorption = _clamp(
        0.01
        + 0.02 * shared_traces
        + 0.06 * heredity
        + 0.08 * selection_pressure
        + 0.04 * governance
        + _noise(rng, 0.015),
        0.0,
        1.0,
    )
    return {
        "adaptation_lag": round(adaptation_lag, 4),
        "post_shift_survival": round(post_shift_survival, 4),
        "recovery_slope": round(recovery_slope, 4),
        "memory_leverage": round(memory_leverage, 4),
        "organization_advantage": round(organization_advantage, 4),
        "heterogeneity_absorption": round(heterogeneity_absorption, 4),
    }


SCENARIO_RUNNERS = {
    "static-baseline": run_static_baseline,
    "regime-shift": run_regime_shift,
    "heterogeneous-brains": run_heterogeneous_brains,
    "memory-timescale-split": run_memory_timescale_split,
}
