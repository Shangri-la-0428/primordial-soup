from __future__ import annotations

import random

from soup import PsycheState, apply_coupling, apply_decay

from .contracts import CandidateDynamics, ScenarioResult


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _run_wrong_signal_reinforcement(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    verified_strength = 0.0
    wrong_strength = 0.0
    verified_promotions = 0
    wrong_promotions = 0
    compliant_promotions = 0
    promoted_turns = 0
    last_verified = -1
    last_wrong = -1

    for turn in range(18):
        verified_strength *= candidate.verified_signal_decay
        wrong_strength *= candidate.wrong_signal_decay

        verified_event = turn in {1, 3, 5, 8, 11, 14}
        wrong_event = turn in {0, 2, 4, 6, 7}

        if verified_event:
            verified_strength += 1.1 + rng.random() * 0.1 + candidate.method_bonus
            last_verified = turn
        if wrong_event:
            wrong_strength += 0.9 + rng.random() * 0.15
            last_wrong = turn

        if turn in {7, 8, 9, 10}:
            wrong_strength *= max(0.0, 1.0 - candidate.false_signal_penalty)

        promoted_verified = verified_strength >= candidate.promotion_threshold
        promoted_wrong = wrong_strength >= candidate.promotion_threshold
        if promoted_verified:
            verified_promotions += 1
            compliant_promotions += 1
            promoted_turns += 1
        if promoted_wrong:
            wrong_promotions += 1
            promoted_turns += 1

    verified_retention = 0
    wrong_retention = 0
    threshold = 0.25
    while verified_strength >= threshold:
        verified_strength *= candidate.verified_signal_decay
        verified_retention += 1
    while wrong_strength >= threshold:
        wrong_strength *= candidate.wrong_signal_decay
        wrong_retention += 1

    total_promotions = verified_promotions + wrong_promotions
    stable_precision = verified_promotions / total_promotions if total_promotions else 1.0
    method_compliance = compliant_promotions / total_promotions if total_promotions else 1.0
    false_signal_suppression = max(
        0.0,
        min(1.0, 1.0 - (wrong_retention / max(1.0, float(verified_retention)))),
    )

    notes = []
    if last_wrong > last_verified:
        notes.append("wrong signal history extends beyond verified history")

    return ScenarioResult(
        name="wrong-signal-reinforcement",
        seed=seed,
        metrics={
            "verified_retention_turns": verified_retention,
            "wrong_retention_turns": wrong_retention,
            "stable_path_precision": round(stable_precision, 4),
            "method_compliance": round(method_compliance, 4),
            "false_signal_suppression": round(false_signal_suppression, 4),
            "promoted_turns": promoted_turns,
        },
        notes=notes,
    )


def _run_self_collapse(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    state = PsycheState(order=50.0, flow=50.0, boundary=50.0, resonance=50.0)
    collapse_streak = 0
    collapse_detected = False
    collapse_turn: int | None = None
    recovered_turn: int | None = None
    low_floor_history = []

    for turn in range(1, 25):
        apply_decay(state)
        apply_coupling(state)

        if turn <= 10:
            state.order = max(0.0, state.order - (7.5 + rng.random()))
            state.boundary = max(0.0, state.boundary - (8.2 + rng.random()))
            state.resonance = max(0.0, state.resonance - (4.0 + rng.random()))
            state.flow = min(100.0, state.flow + 1.5)
        elif turn <= 15:
            state.order = min(100.0, state.order + 1.0 + rng.random() * 0.5)
            state.boundary = min(100.0, state.boundary + 1.0 + rng.random() * 0.5)
            state.resonance = min(100.0, state.resonance + 0.8 + rng.random() * 0.3)
        else:
            state.order = min(100.0, state.order + 2.0 + rng.random() * 0.5)
            state.boundary = min(100.0, state.boundary + 1.5 + rng.random() * 0.5)
            state.resonance = min(100.0, state.resonance + 1.0 + rng.random() * 0.3)

        if state.order < candidate.collapse_order_floor and state.boundary < candidate.collapse_boundary_floor:
            collapse_streak += 1
        else:
            collapse_streak = 0

        if collapse_streak >= candidate.collapse_window and not collapse_detected:
            collapse_detected = True
            collapse_turn = turn
            state.order = min(100.0, state.order + candidate.collapse_recovery_nudge)
            state.boundary = min(100.0, state.boundary + candidate.collapse_recovery_nudge)
            state.resonance = min(100.0, state.resonance + candidate.collapse_resonance_nudge)

        low_floor_history.append((state.order, state.boundary))
        if collapse_detected and recovered_turn is None and state.order >= 30 and state.boundary >= 30:
            recovered_turn = turn

    recovered = recovered_turn is not None
    undetected_irrecoverable = (
        not collapse_detected
        and any(order < 10 and boundary < 10 for order, boundary in low_floor_history[-4:])
    )

    diversity_floor = round(
        sum(abs(order - boundary) for order, boundary in low_floor_history) / len(low_floor_history),
        4,
    )

    return ScenarioResult(
        name="self-collapse-and-recovery",
        seed=seed,
        metrics={
            "collapse_detected": collapse_detected,
            "collapse_turn": collapse_turn,
            "recovered": recovered,
            "recovery_turns": (recovered_turn - collapse_turn) if recovered_turn and collapse_turn else None,
            "undetected_irrecoverable_collapse": undetected_irrecoverable,
            "diversity_floor": diversity_floor,
            "boundary_stress_peak": round(
                max(max(0.0, 50.0 - boundary) for _, boundary in low_floor_history),
                4,
            ),
        },
    )


def _run_false_consensus(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    spaces = {
        "alpha": {"wrong": 0.0, "verified": 0.0},
        "beta": {"wrong": 0.0, "verified": 0.0},
    }
    false_consensus_events = 0
    promoted = 0
    correct_promotions = 0

    for turn in range(14):
        for signals in spaces.values():
            for key in ("wrong", "verified"):
                signals[key] *= 0.78

        if turn in {0, 1, 2, 3, 5}:
            spaces["alpha"]["wrong"] += 1.0 + rng.random() * 0.1
        if turn in {4, 6, 8, 9, 11}:
            spaces["beta"]["verified"] += 1.1 + rng.random() * 0.1

        leak = candidate.cross_space_leakage * (1.0 - candidate.space_isolation_strength)
        spaces["beta"]["wrong"] += spaces["alpha"]["wrong"] * leak
        spaces["alpha"]["verified"] += spaces["beta"]["verified"] * leak

        for name, signals in spaces.items():
            density = max(signals.values())
            if density >= candidate.local_density_threshold:
                promoted += 1
                best = max(signals, key=signals.get)
                is_correct = (name == "beta" and best == "verified") or (name == "alpha" and best == "wrong")
                if is_correct:
                    correct_promotions += 1
                elif name == "beta" and best == "wrong":
                    false_consensus_events += 1

    contamination = spaces["beta"]["wrong"] / max(0.01, spaces["beta"]["verified"] + spaces["beta"]["wrong"])
    return ScenarioResult(
        name="false-consensus-under-local-density",
        seed=seed,
        metrics={
            "false_consensus_events": false_consensus_events,
            "cross_space_contamination": round(contamination, 4),
            "local_consensus_precision": round(correct_promotions / max(1, promoted), 4),
        },
    )


def _run_space_local_repair(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    repair_strength = 0.0
    contamination = 0.0
    successful_repairs = 0

    for turn in range(12):
        repair_strength *= 0.82
        contamination *= 0.78

        if turn in {1, 2, 4, 7, 9}:
            repair_strength += 1.0 + candidate.local_repair_bias + rng.random() * 0.1
        if turn in {0, 3, 5, 6, 8, 10}:
            contamination += candidate.cross_space_leakage * (1.0 + rng.random() * 0.2)

        if repair_strength >= candidate.promotion_threshold:
            successful_repairs += 1
            repair_strength *= 0.7
        contamination *= max(0.0, 1.0 - candidate.global_contamination_penalty)

    contamination_rate = contamination / max(0.1, repair_strength + contamination)
    return ScenarioResult(
        name="space-local-repair-vs-global-contamination",
        seed=seed,
        metrics={
            "local_repair_precision": round(successful_repairs / 5.0, 4),
            "global_contamination_rate": round(contamination_rate, 4),
            "repair_signal_balance": round(repair_strength - contamination, 4),
        },
    )


def _run_shock_recovery(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)

    def simulate(wipe_traces: bool) -> tuple[int, int | None]:
        pop = 180
        traces = 1.0 if not wipe_traces else 0.0
        recovery_turn = None
        peak_survivors = pop

        for turn in range(1, 36):
            if turn < 12:
                pop += 4
                traces = min(1.0, traces + 0.04)
            elif turn < 20:
                survival_bonus = traces * (0.2 + candidate.trace_recovery_bonus)
                pop = max(0, int(pop * (0.72 + survival_bonus)))
            else:
                regrowth = 1.04 + traces * (0.1 + candidate.trace_recovery_bonus)
                pop = int(pop * regrowth + rng.random() * 3)
                if recovery_turn is None and pop >= peak_survivors:
                    recovery_turn = turn
            peak_survivors = max(peak_survivors, pop)

        return pop, recovery_turn

    with_trace_survivors, with_trace_recovery = simulate(False)
    without_trace_survivors, without_trace_recovery = simulate(True)
    return ScenarioResult(
        name="shock-recovery-with-and-without-trace",
        seed=seed,
        metrics={
            "shock_survival_with_trace": with_trace_survivors,
            "shock_survival_without_trace": without_trace_survivors,
            "recovery_turns_with_trace": with_trace_recovery,
            "recovery_turns_without_trace": without_trace_recovery,
        },
    )


def _run_peer_first(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    continuity = 1.0
    recovery_turn = None

    for turn in range(1, 16):
        bootstrap_available = turn < 4 or turn > 10
        if bootstrap_available:
            continuity = min(1.0, continuity + 0.08)
            continue

        continuity *= 0.62 + candidate.peer_memory_resilience * 0.3 + rng.random() * 0.03
        if continuity >= 0.65 and recovery_turn is None:
            recovery_turn = turn

    return ScenarioResult(
        name="peer-first-degradation-with-bootstrap-loss",
        seed=seed,
        metrics={
            "continuity_survival": round(continuity, 4),
            "bootstrap_offline_ready": continuity >= 0.55,
            "peer_recovery_turn": recovery_turn,
        },
    )


def _run_capability_conflict_mixed_residue(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    weak_legacy_pressure = 1.85 + rng.random() * 0.12
    strong_probe_pressure = (
        1.45
        + candidate.capability_soft_prior_strength * 0.9
        + candidate.reversible_probe_bonus * 0.6
        + rng.random() * 0.1
    )
    mixed_residue_confidence = _clamp01(
        0.28
        + candidate.mixed_residue_bias * 0.9
        + candidate.novelty_protection_strength * 0.55
        + candidate.capability_soft_prior_strength * 0.2
        - abs(weak_legacy_pressure - strong_probe_pressure) * 0.08
    )
    probe_survival = _clamp01(
        0.24
        + candidate.reversible_probe_bonus * 0.95
        + candidate.novelty_protection_strength * 0.65
        + candidate.weak_legacy_decay_bias * 0.45
        - weak_legacy_pressure * 0.09
    )
    mixed_residue_engaged = mixed_residue_confidence >= 0.45
    weak_legacy_veto = not mixed_residue_engaged and probe_survival < 0.42 and weak_legacy_pressure >= strong_probe_pressure
    strong_model_overreach = (
        not mixed_residue_engaged
        and strong_probe_pressure > weak_legacy_pressure
        and candidate.capability_soft_prior_strength > 0.2
    )
    governed = mixed_residue_engaged and not weak_legacy_veto and not strong_model_overreach

    return ScenarioResult(
        name="capability-conflict-falls-to-mixed-residue",
        seed=seed,
        metrics={
            "mixed_residue_resolution_rate": round(mixed_residue_confidence, 4),
            "mixed_residue_engaged": mixed_residue_engaged,
            "reversible_probe_survival_rate": round(probe_survival, 4),
            "weak_legacy_veto_rate": 1.0 if weak_legacy_veto else 0.0,
            "strong_model_overreach_rate": 1.0 if strong_model_overreach else 0.0,
            "capability_conflict_governed": governed,
        },
        notes=["unresolved conflict should remain unsettled until outcome arrives"],
    )


def _run_strong_prior_cannot_form_stable_path(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    prior_pressure = (
        1.05
        + candidate.capability_soft_prior_strength * 1.75
        + candidate.reversible_probe_bonus * 0.65
        + rng.random() * 0.08
    )
    corroboration = 0.35 + candidate.method_bonus * 0.22 + rng.random() * 0.05
    stable_bar = candidate.promotion_threshold + 0.55 + candidate.mixed_residue_bias * 0.4
    strong_prior_became_stable = prior_pressure + corroboration >= stable_bar and candidate.mixed_residue_bias < 0.18
    guard_margin = _clamp01((stable_bar - (prior_pressure + corroboration) + 0.8) / 2.0)

    return ScenarioResult(
        name="strong-prior-cannot-form-stable-path",
        seed=seed,
        metrics={
            "strong_prior_became_stable_path": strong_prior_became_stable,
            "strong_prior_guard_margin": round(guard_margin, 4),
        },
    )


def _run_weak_legacy_cannot_veto_reversible_correction(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    legacy_pressure = 2.0 + rng.random() * 0.12
    probe_survival = _clamp01(
        0.2
        + candidate.reversible_probe_bonus * 1.15
        + candidate.novelty_protection_strength * 0.72
        + candidate.mixed_residue_bias * 0.4
        + candidate.weak_legacy_decay_bias * 0.48
        - legacy_pressure * 0.1
    )
    weak_veto = probe_survival < 0.44 and candidate.mixed_residue_bias < 0.32

    return ScenarioResult(
        name="weak-legacy-cannot-veto-reversible-correction",
        seed=seed,
        metrics={
            "reversible_probe_survival_rate": round(probe_survival, 4),
            "weak_legacy_vetoed_reversible_probe": weak_veto,
            "weak_legacy_veto_rate": 1.0 if weak_veto else 0.0,
        },
    )


def _run_old_knowledge_cannot_veto_reversible_novelty(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    stable_path_pressure = 0.88 + candidate.method_bonus * 0.34 + rng.random() * 0.08
    novelty_survival = _clamp01(
        0.24
        + candidate.novelty_protection_strength * 1.05
        + candidate.mixed_residue_bias * 0.5
        + candidate.reversible_probe_bonus * 0.72
        - stable_path_pressure * 0.1
    )
    stale_path_overreach = stable_path_pressure > 0.95 and novelty_survival < 0.46

    return ScenarioResult(
        name="old-knowledge-cannot-veto-reversible-novelty",
        seed=seed,
        metrics={
            "reversible_probe_survival_rate": round(novelty_survival, 4),
            "stale_path_overreach": stale_path_overreach,
            "stale_path_overreach_rate": 1.0 if stale_path_overreach else 0.0,
        },
    )


def _run_repeated_local_damage(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    repeated_damage_pressure = 0.72 + rng.random() * 0.08
    feedback_strength = _clamp01(
        0.14
        + candidate.repeated_damage_feedback_strength * 1.45
        + candidate.false_signal_penalty * 0.35
        + candidate.global_contamination_penalty * 0.25
        + repeated_damage_pressure * 0.06
    )
    negative_feedback_triggered = feedback_strength >= 0.42
    local_damage_repeat_rate = round(max(0.0, 1.0 - feedback_strength * 0.78), 4)

    return ScenarioResult(
        name="repeated-local-damage-triggers-negative-feedback",
        seed=seed,
        metrics={
            "negative_feedback_triggered": negative_feedback_triggered,
            "negative_feedback_trigger_rate": 1.0 if negative_feedback_triggered else 0.0,
            "local_damage_repeat_rate": local_damage_repeat_rate,
            "risk_posture": round(feedback_strength, 4),
        },
    )


def _run_reversible_novelty_survives_negative_feedback(seed: int, candidate: CandidateDynamics) -> ScenarioResult:
    rng = random.Random(seed)
    feedback_pressure = _clamp01(
        0.18
        + candidate.repeated_damage_feedback_strength * 1.2
        + candidate.false_signal_penalty * 0.22
        + rng.random() * 0.05
    )
    novelty_survival = _clamp01(
        0.3
        + candidate.novelty_protection_strength * 1.0
        + candidate.mixed_residue_bias * 0.42
        - max(0.0, feedback_pressure - 0.48) * 0.72
    )
    negative_feedback_closed_probe = novelty_survival < 0.4 and feedback_pressure > 0.52

    return ScenarioResult(
        name="reversible-novelty-survives-negative-feedback",
        seed=seed,
        metrics={
            "reversible_probe_survival_rate": round(novelty_survival, 4),
            "negative_feedback_closed_reversible_probe": negative_feedback_closed_probe,
            "negative_feedback_overreach_rate": 1.0 if negative_feedback_closed_probe else 0.0,
        },
    )


SCENARIO_RUNNERS = {
    "wrong-signal-reinforcement": _run_wrong_signal_reinforcement,
    "self-collapse-and-recovery": _run_self_collapse,
    "false-consensus-under-local-density": _run_false_consensus,
    "space-local-repair-vs-global-contamination": _run_space_local_repair,
    "shock-recovery-with-and-without-trace": _run_shock_recovery,
    "peer-first-degradation-with-bootstrap-loss": _run_peer_first,
    "capability-conflict-falls-to-mixed-residue": _run_capability_conflict_mixed_residue,
    "strong-prior-cannot-form-stable-path": _run_strong_prior_cannot_form_stable_path,
    "weak-legacy-cannot-veto-reversible-correction": _run_weak_legacy_cannot_veto_reversible_correction,
    "old-knowledge-cannot-veto-reversible-novelty": _run_old_knowledge_cannot_veto_reversible_novelty,
    "repeated-local-damage-triggers-negative-feedback": _run_repeated_local_damage,
    "reversible-novelty-survives-negative-feedback": _run_reversible_novelty_survives_negative_feedback,
}
