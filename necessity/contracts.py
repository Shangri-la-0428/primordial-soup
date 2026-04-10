from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from harness import DEFAULT_SEEDS


ALL_NECESSITY_SCENARIOS = (
    "static-baseline",
    "regime-shift",
    "heterogeneous-brains",
    "memory-timescale-split",
)
DEFAULT_NECESSITY_SCENARIOS = (
    "regime-shift",
    "heterogeneous-brains",
    "memory-timescale-split",
)
DEFAULT_NECESSITY_SEEDS = DEFAULT_SEEDS


@dataclass(frozen=True, slots=True)
class SystemStack:
    name: str
    private_state: bool = False
    shared_traces: bool = False
    heredity: bool = False
    selection_pressure: bool = False
    heterogeneity_governance: bool = False


NECESSITY_STACKS = {
    "fixed-policy": SystemStack(name="fixed-policy"),
    "fixed-policy + private state": SystemStack(
        name="fixed-policy + private state",
        private_state=True,
    ),
    "fixed-policy + shared traces": SystemStack(
        name="fixed-policy + shared traces",
        shared_traces=True,
    ),
    "fixed-policy + shared traces + heredity": SystemStack(
        name="fixed-policy + shared traces + heredity",
        shared_traces=True,
        heredity=True,
    ),
    "shared traces + heredity + selection pressure": SystemStack(
        name="shared traces + heredity + selection pressure",
        private_state=True,
        shared_traces=True,
        heredity=True,
        selection_pressure=True,
        heterogeneity_governance=True,
    ),
}


@dataclass(frozen=True, slots=True)
class NecessityClaim:
    id: str
    statement: str
    control_stack: str
    open_stack: str
    failure_condition: str


DEFAULT_NECESSITY_CLAIMS = (
    NecessityClaim(
        id="C1",
        statement="固定决策映射在 regime shift 下会失效",
        control_stack="fixed-policy",
        open_stack="shared traces + heredity + selection pressure",
        failure_condition="开放组没有明显缩短 adaptation_lag，也没有提高 post-shift survival 与 recovery slope",
    ),
    NecessityClaim(
        id="C2",
        statement="只有个体内状态还不够，必须有共享环境记忆",
        control_stack="fixed-policy + private state",
        open_stack="fixed-policy + shared traces",
        failure_condition="开放组没有显著提高 memory leverage，且 regime shift 后的生存率没有改善",
    ),
    NecessityClaim(
        id="C3",
        statement="只有共享记忆还不够，必须允许跨代保留有效偏置",
        control_stack="fixed-policy + shared traces",
        open_stack="fixed-policy + shared traces + heredity",
        failure_condition="开放组没有显著提高 recovery slope，也没有降低 memory-timescale-split 下的退化",
    ),
    NecessityClaim(
        id="C4",
        statement="能力异构存在时，系统必须进化的是吸收差异的组织律，而不是某个单体答案",
        control_stack="fixed-policy + shared traces + heredity",
        open_stack="shared traces + heredity + selection pressure",
        failure_condition="开放组没有显著提高 heterogeneity absorption 与 organization advantage",
    ),
)


@dataclass(slots=True)
class NecessityScenarioResult:
    claim_id: str
    scenario: str
    control_metrics: dict[str, float]
    open_metrics: dict[str, float]
    necessity_holds: bool


@dataclass(slots=True)
class NecessityReport:
    generated_at: str
    claims: list[NecessityClaim]
    scenario_results: list[NecessityScenarioResult]
    conclusions: list[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "generated_at": self.generated_at,
                "claims": [asdict(claim) for claim in self.claims],
                "scenario_results": [asdict(result) for result in self.scenario_results],
                "conclusions": self.conclusions,
            },
            indent=2,
        )
