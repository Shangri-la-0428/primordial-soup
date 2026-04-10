from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


FROZEN_IDENTITY_PRIMITIVES = ("principal", "account", "delegate", "session")
FROZEN_SHARED_CARRIERS = ("trace", "signal", "policy", "view")
FROZEN_DIMENSIONS = (
    "scope",
    "reversibility",
    "authority_basis",
    "corroboration_scope",
    "risk_posture",
)
FROZEN_SIGNAL_KINDS = ("recommend", "avoid", "watch", "info")
FROZEN_TRACE_TAXONOMY = ("coordination", "continuity", "calibration")
FROZEN_EVIDENCE_STATES = ("stable-path", "mixed-residue")
FROZEN_LAYER_ROLES = {
    "Psyche": "private-subjective-continuity",
    "Thronglets": "shared-sparse-environment",
    "Oasyce": "low-frequency-authorization-commitment-settlement",
}
DEFAULT_SCENARIOS = (
    "wrong-signal-reinforcement",
    "self-collapse-and-recovery",
    "false-consensus-under-local-density",
    "space-local-repair-vs-global-contamination",
    "shock-recovery-with-and-without-trace",
    "peer-first-degradation-with-bootstrap-loss",
    "capability-conflict-falls-to-mixed-residue",
    "strong-prior-cannot-form-stable-path",
    "weak-legacy-cannot-veto-reversible-correction",
    "old-knowledge-cannot-veto-reversible-novelty",
    "repeated-local-damage-triggers-negative-feedback",
    "reversible-novelty-survives-negative-feedback",
)
DEFAULT_SEEDS = (42, 7, 123)
ALLOWED_EXISTING_NOUNS = set(FROZEN_IDENTITY_PRIMITIVES) | set(FROZEN_SHARED_CARRIERS) | {
    "stable-path",
    "mixed-residue",
    "Psyche",
    "Thronglets",
    "Oasyce",
}
PROMOTION_METRIC_LABELS = {
    "join_gain": "join gain",
    "poison_resistance": "poison resistance",
    "innovation_preservation": "innovation preservation",
    "capability_conflict_governance": "capability conflict governance",
    "stable_path_precision": "stable-path precision",
    "method_compliance": "method compliance",
}


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(slots=True)
class ConceptMapping:
    carrier: str = "trace"
    dimensions: tuple[str, ...] = ("risk_posture",)
    public_surface_change: bool = False
    new_nouns: tuple[str, ...] = ()


def default_concept_mapping() -> ConceptMapping:
    return ConceptMapping()


@dataclass(slots=True)
class CandidateDynamics:
    name: str
    description: str
    identity_primitives: tuple[str, ...] = FROZEN_IDENTITY_PRIMITIVES
    signal_kinds: tuple[str, ...] = FROZEN_SIGNAL_KINDS
    trace_taxonomy: tuple[str, ...] = FROZEN_TRACE_TAXONOMY
    external_continuity_version: int = 1
    introduces_new_ontology: bool = False
    hot_path_chain_dependency: bool = False
    shared_high_frequency_private_state: bool = False
    concept_mapping: ConceptMapping = field(default_factory=default_concept_mapping)
    collapse_window: int = 4
    collapse_order_floor: float = 18.0
    collapse_boundary_floor: float = 18.0
    collapse_recovery_nudge: float = 0.0
    collapse_resonance_nudge: float = 0.0
    verified_signal_decay: float = 0.88
    wrong_signal_decay: float = 0.88
    promotion_threshold: float = 2.0
    false_signal_penalty: float = 0.0
    method_bonus: float = 0.0
    space_isolation_strength: float = 0.65
    cross_space_leakage: float = 0.22
    local_density_threshold: float = 2.0
    local_repair_bias: float = 0.0
    global_contamination_penalty: float = 0.0
    trace_recovery_bonus: float = 0.0
    peer_memory_resilience: float = 0.45
    capability_soft_prior_strength: float = 0.08
    reversible_probe_bonus: float = 0.08
    weak_legacy_decay_bias: float = 0.08
    mixed_residue_bias: float = 0.12
    novelty_protection_strength: float = 0.12
    repeated_damage_feedback_strength: float = 0.18


def control_candidate() -> CandidateDynamics:
    return CandidateDynamics(
        name="control-baseline",
        description="Frozen stack boundary with minimal safeguards and neutral dynamics.",
    )


def guarded_candidate() -> CandidateDynamics:
    return CandidateDynamics(
        name="guarded-emergence-v2",
        description=(
            "Ontology-convergent profile with stronger false-signal suppression, "
            "mixed-residue discipline, reversible novelty protection, and "
            "capability-aware soft priors."
        ),
        concept_mapping=ConceptMapping(
            carrier="trace",
            dimensions=("risk_posture", "reversibility", "authority_basis"),
        ),
        collapse_recovery_nudge=7.0,
        collapse_resonance_nudge=2.0,
        verified_signal_decay=0.92,
        wrong_signal_decay=0.56,
        promotion_threshold=2.6,
        false_signal_penalty=0.42,
        method_bonus=0.25,
        space_isolation_strength=0.93,
        cross_space_leakage=0.04,
        local_density_threshold=2.6,
        local_repair_bias=0.22,
        global_contamination_penalty=0.2,
        trace_recovery_bonus=0.32,
        peer_memory_resilience=0.8,
        capability_soft_prior_strength=0.28,
        reversible_probe_bonus=0.32,
        weak_legacy_decay_bias=0.34,
        mixed_residue_bias=0.42,
        novelty_protection_strength=0.46,
        repeated_damage_feedback_strength=0.46,
    )


def candidate_from_payload(
    data: dict[str, Any],
    base_candidate: CandidateDynamics | None = None,
) -> CandidateDynamics:
    base = asdict(base_candidate or guarded_candidate())
    merged = _deep_merge(base, data)
    tuple_fields = {"identity_primitives", "signal_kinds", "trace_taxonomy"}
    for key in tuple_fields:
        if key in merged and isinstance(merged[key], list):
            merged[key] = tuple(merged[key])
    concept_mapping = merged.get("concept_mapping", {})
    if isinstance(concept_mapping, dict):
        if isinstance(concept_mapping.get("dimensions"), list):
            concept_mapping["dimensions"] = tuple(concept_mapping["dimensions"])
        if isinstance(concept_mapping.get("new_nouns"), list):
            concept_mapping["new_nouns"] = tuple(concept_mapping["new_nouns"])
        merged["concept_mapping"] = ConceptMapping(**concept_mapping)
    elif isinstance(concept_mapping, ConceptMapping):
        merged["concept_mapping"] = concept_mapping
    return CandidateDynamics(**merged)


def load_candidate_from_json(path: str) -> CandidateDynamics:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return candidate_from_payload(data)


@dataclass(slots=True)
class ScenarioResult:
    name: str
    seed: int
    metrics: dict[str, float | int | bool | None]
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CandidateSummary:
    candidate: str
    concept_mapping: ConceptMapping
    metrics: dict[str, float]
    ontology_gate_failures: list[str]
    mechanism_gate_failures: list[str]
    improvements: list[str]
    passes_ontology_gate: bool
    passes_mechanism_gate: bool
    passes_gate: bool


@dataclass(slots=True)
class HarnessReport:
    boundary_contract: dict[str, Any]
    seeds: tuple[int, ...]
    scenarios: tuple[str, ...]
    control: CandidateSummary
    candidate: CandidateSummary
    scenario_results: dict[str, dict[str, list[ScenarioResult]]]

    def to_json(self) -> str:
        return json.dumps(
            {
                "boundary_contract": self.boundary_contract,
                "seeds": list(self.seeds),
                "scenarios": list(self.scenarios),
                "control": asdict(self.control),
                "candidate": asdict(self.candidate),
                "scenario_results": {
                    side: {
                        name: [asdict(result) for result in results]
                        for name, results in scenario_map.items()
                    }
                    for side, scenario_map in self.scenario_results.items()
                },
            },
            indent=2,
        )


def boundary_contract_snapshot() -> dict[str, Any]:
    return {
        "identity_primitives": list(FROZEN_IDENTITY_PRIMITIVES),
        "shared_carriers": list(FROZEN_SHARED_CARRIERS),
        "control_dimensions": list(FROZEN_DIMENSIONS),
        "signal_kinds": list(FROZEN_SIGNAL_KINDS),
        "trace_taxonomy": list(FROZEN_TRACE_TAXONOMY),
        "evidence_states": list(FROZEN_EVIDENCE_STATES),
        "layer_roles": FROZEN_LAYER_ROLES,
        "external_continuity_version": 1,
    }


def validate_ontology_gate(candidate: CandidateDynamics) -> list[str]:
    failures: list[str] = []
    mapping = candidate.concept_mapping

    if tuple(candidate.identity_primitives) != FROZEN_IDENTITY_PRIMITIVES:
        failures.append("identity primitives must remain principal/account/delegate/session")
    if tuple(candidate.signal_kinds) != FROZEN_SIGNAL_KINDS:
        failures.append("signal kinds must remain recommend/avoid/watch/info")
    if tuple(candidate.trace_taxonomy) != FROZEN_TRACE_TAXONOMY:
        failures.append("trace taxonomy must remain coordination/continuity/calibration")
    if candidate.external_continuity_version != 1:
        failures.append("external continuity contract must remain version 1")
    if candidate.introduces_new_ontology:
        failures.append("candidate introduces a new ontology")
    if candidate.hot_path_chain_dependency:
        failures.append("candidate adds a hot-path chain dependency")
    if candidate.shared_high_frequency_private_state:
        failures.append("candidate leaks high-frequency private state into the shared substrate")
    if mapping.carrier not in FROZEN_SHARED_CARRIERS:
        failures.append(
            f"concept mapping carrier must remain one of {', '.join(FROZEN_SHARED_CARRIERS)}"
        )
    invalid_dimensions = [
        dimension for dimension in mapping.dimensions if dimension not in FROZEN_DIMENSIONS
    ]
    if not mapping.dimensions:
        failures.append("concept mapping must declare at least one frozen control dimension")
    if invalid_dimensions:
        failures.append(
            "concept mapping dimensions must remain within " + ", ".join(FROZEN_DIMENSIONS)
        )
    if mapping.public_surface_change:
        failures.append("candidate widens the public surface")
    if mapping.new_nouns:
        unmapped = [noun for noun in mapping.new_nouns if noun not in ALLOWED_EXISTING_NOUNS]
        if unmapped:
            failures.append(
                "candidate introduces unmappable nouns: " + ", ".join(sorted(unmapped))
            )
        failures.append("candidate must not introduce new nouns")
    return failures
