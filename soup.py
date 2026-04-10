"""Primordial Soup — evolution simulation derived from Sigil axioms.

Three axioms drive everything:
  1. Existence: a Cell is a causal closure (state → decision → action → state change)
  2. Transformation: FORK/BOND/DISSOLVE reshape the population graph
  3. Sovereignty: no external controller; behavior = genome × psyche × perception

Zero external dependencies. Pure Python 3.10+ standard library.
(LLMEngine uses urllib from stdlib — no pip install needed.)
"""

from __future__ import annotations

import json
import math
import random
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Protocol, Any

from model_lane import LLMConfig, get_transport_adapter


# ════════════════════════════════════════════════════════════════
#  Genome — unit of heredity
# ════════════════════════════════════════════════════════════════

@dataclass
class Genome:
    fork_threshold: float    # [0.3, 0.9] energy ratio to attempt reproduction
    exploration_rate: float  # [0, 1] random vs directed search
    cooperation_bias: float  # [0, 1] tendency to BOND
    signal_frequency: float  # [0, 1] probability of emitting trace
    risk_tolerance: float    # [0, 1] decision temperature / search distance
    aptitude: float          # [0, 1] 0=scout(wide signal) ↔ 1=hunter(efficient search)

    def mutate(self, sigma: float) -> Genome:
        def _m(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v + random.gauss(0, sigma)))
        return Genome(
            fork_threshold=_m(self.fork_threshold, 0.3, 0.9),
            exploration_rate=_m(self.exploration_rate, 0.0, 1.0),
            cooperation_bias=_m(self.cooperation_bias, 0.0, 1.0),
            signal_frequency=_m(self.signal_frequency, 0.0, 1.0),
            risk_tolerance=_m(self.risk_tolerance, 0.0, 1.0),
            aptitude=_m(self.aptitude, 0.0, 1.0),
        )

    @staticmethod
    def random() -> Genome:
        return Genome(
            fork_threshold=random.uniform(0.3, 0.9),
            exploration_rate=random.random(),
            cooperation_bias=random.random(),
            signal_frequency=random.random(),
            risk_tolerance=random.random(),
            aptitude=random.random(),
        )

    def weights(self) -> list[float]:
        return [self.fork_threshold, self.exploration_rate,
                self.cooperation_bias, self.signal_frequency,
                self.risk_tolerance, self.aptitude]


# ════════════════════════════════════════════════════════════════
#  NeuralGenome — evolvable neural network (Phase 7)
# ════════════════════════════════════════════════════════════════

class NeuralGenome:
    """Small neural network as genome. The genome IS the decision function.
    16 inputs → 8 hidden (tanh) → 6 outputs. 190 evolvable weights."""

    INPUT_SIZE = 16
    HIDDEN_SIZE = 8
    OUTPUT_SIZE = 6  # SEARCH, HARVEST, FORK, BOND, SIGNAL, REST

    def __init__(self, w1: list[list[float]] | None = None,
                 b1: list[float] | None = None,
                 w2: list[list[float]] | None = None,
                 b2: list[float] | None = None):
        if w1 is None:
            # He initialization
            s1 = math.sqrt(2.0 / self.INPUT_SIZE)
            s2 = math.sqrt(2.0 / self.HIDDEN_SIZE)
            self.w1 = [[random.gauss(0, s1) for _ in range(self.INPUT_SIZE)]
                        for _ in range(self.HIDDEN_SIZE)]
            self.b1 = [0.0] * self.HIDDEN_SIZE
            self.w2 = [[random.gauss(0, s2) for _ in range(self.HIDDEN_SIZE)]
                        for _ in range(self.OUTPUT_SIZE)]
            self.b2 = [0.0] * self.OUTPUT_SIZE
        else:
            self.w1, self.b1, self.w2, self.b2 = w1, b1, w2, b2

    def forward(self, inputs: list[float]) -> list[float]:
        hidden = []
        for j in range(self.HIDDEN_SIZE):
            z = self.b1[j]
            for i in range(self.INPUT_SIZE):
                z += self.w1[j][i] * inputs[i]
            hidden.append(math.tanh(z))
        output = []
        for k in range(self.OUTPUT_SIZE):
            z = self.b2[k]
            for j in range(self.HIDDEN_SIZE):
                z += self.w2[k][j] * hidden[j]
            output.append(z)
        return output

    def mutate(self, sigma: float) -> NeuralGenome:
        def _m(v: float) -> float:
            return v + random.gauss(0, sigma)
        new_w1 = [[_m(v) for v in row] for row in self.w1]
        new_b1 = [_m(v) for v in self.b1]
        new_w2 = [[_m(v) for v in row] for row in self.w2]
        new_b2 = [_m(v) for v in self.b2]
        return NeuralGenome(new_w1, new_b1, new_w2, new_b2)

    def weights(self) -> list[float]:
        flat: list[float] = []
        for row in self.w1:
            flat.extend(row)
        flat.extend(self.b1)
        for row in self.w2:
            flat.extend(row)
        flat.extend(self.b2)
        return flat

    @staticmethod
    def random() -> NeuralGenome:
        return NeuralGenome()

    def param_count(self) -> int:
        return (self.INPUT_SIZE * self.HIDDEN_SIZE + self.HIDDEN_SIZE +
                self.HIDDEN_SIZE * self.OUTPUT_SIZE + self.OUTPUT_SIZE)


# ════════════════════════════════════════════════════════════════
#  PsycheState — simplified 4D self-state (from Psyche v11)
# ════════════════════════════════════════════════════════════════

BASELINE = 50.0

# Decay factors per tick (ported from chemistry.ts DIMENSION_SPECS)
DECAY = {"order": 0.9952, "flow": 0.9967, "boundary": 0.9991, "resonance": 0.9979}

# Coupling rate (from applyMutualInfluence)
COUPLING_RATE = 0.03


@dataclass
class PsycheState:
    order: float = 50.0       # 序 — internal coherence
    flow: float = 50.0        # 流 — exchange with environment
    boundary: float = 50.0    # 界 — self/non-self distinction
    resonance: float = 50.0   # 振 — attunement with others

    def values(self) -> list[float]:
        return [self.order, self.flow, self.boundary, self.resonance]


@dataclass
class Overlay:
    """Projected from 4D state. Modulates decisions without being 'read'."""
    arousal: float = 0.0      # [-1, 1] activation level
    valence: float = 0.0      # [-1, 1] positive/negative affect
    agency: float = 0.0       # [-1, 1] sense of control
    vulnerability: float = 0.0  # [0, 1] openness to disruption


def compute_overlay(ps: PsycheState) -> Overlay:
    o, f, b, r = ps.order - BASELINE, ps.flow - BASELINE, ps.boundary - BASELINE, ps.resonance - BASELINE
    return Overlay(
        arousal=max(-1.0, min(1.0, (f + o) / 100)),
        valence=max(-1.0, min(1.0, (o + r) / 100)),
        agency=max(-1.0, min(1.0, (b + o) / 100)),
        vulnerability=max(0.0, min(1.0, (-b - o) / 100 + 0.5)),
    )


def apply_decay(ps: PsycheState) -> PsycheState:
    """Each dimension decays toward baseline at its own rate."""
    ps.order = BASELINE + (ps.order - BASELINE) * DECAY["order"]
    ps.flow = BASELINE + (ps.flow - BASELINE) * DECAY["flow"]
    ps.boundary = BASELINE + (ps.boundary - BASELINE) * DECAY["boundary"]
    ps.resonance = BASELINE + (ps.resonance - BASELINE) * DECAY["resonance"]
    return ps


def apply_coupling(ps: PsycheState) -> PsycheState:
    """Dimensions influence each other (from applyMutualInfluence)."""
    # Low order drags boundary down
    if ps.order < BASELINE:
        drag = (BASELINE - ps.order) / BASELINE * COUPLING_RATE
        ps.boundary -= drag * BASELINE

    # High flow raises order
    if ps.flow > BASELINE:
        lift = (ps.flow - BASELINE) / BASELINE * COUPLING_RATE
        ps.order += lift * BASELINE

    # High resonance stabilizes boundary
    if ps.resonance > BASELINE:
        stabilize = (ps.resonance - BASELINE) / BASELINE * COUPLING_RATE
        ps.boundary += stabilize * BASELINE

    # Clamp all to [0, 100]
    ps.order = max(0.0, min(100.0, ps.order))
    ps.flow = max(0.0, min(100.0, ps.flow))
    ps.boundary = max(0.0, min(100.0, ps.boundary))
    ps.resonance = max(0.0, min(100.0, ps.resonance))
    return ps


# Stimulus vectors: action → psyche delta
STIMULUS = {
    "SEARCH_OK":    {"order": 3, "flow": 5, "boundary": 0, "resonance": 0},
    "SEARCH_FAIL":  {"order": -2, "flow": 2, "boundary": 0, "resonance": 0},
    "HARVEST_OK":   {"order": 5, "flow": 8, "boundary": 0, "resonance": 8},
    "HARVEST_FAIL": {"order": -3, "flow": 3, "boundary": 2, "resonance": -3},
    "FORK":         {"order": -5, "flow": 8, "boundary": 3, "resonance": 0},
    "BOND":         {"order": 0, "flow": 5, "boundary": -3, "resonance": 10},
    "SIGNAL":       {"order": 0, "flow": 2, "boundary": 0, "resonance": 3},
    "REST":         {"order": 4, "flow": -2, "boundary": 0, "resonance": 0},
}


def apply_stimulus(ps: PsycheState, key: str) -> PsycheState:
    d = STIMULUS.get(key, {})
    ps.order = max(0.0, min(100.0, ps.order + d.get("order", 0)))
    ps.flow = max(0.0, min(100.0, ps.flow + d.get("flow", 0)))
    ps.boundary = max(0.0, min(100.0, ps.boundary + d.get("boundary", 0)))
    ps.resonance = max(0.0, min(100.0, ps.resonance + d.get("resonance", 0)))
    return ps


# ════════════════════════════════════════════════════════════════
#  Environment — the primordial soup
# ════════════════════════════════════════════════════════════════

Pos = tuple[int, int]


@dataclass
class SignalTrace:
    position: Pos
    emitter_id: str
    kind: str            # "resource" | "deposit" | "bond"
    payload: Pos | None  # the actual information: location of the thing
    strength: float
    age: int = 0
    reinforcements: int = 0  # how many times reinforced → becomes Trace


@dataclass
class LocalPerception:
    nearby_resources: list[tuple[Pos, float]]   # (position, amount)
    nearby_deposits: list[tuple[Pos, float]]    # rich deposits (need cooperation)
    nearby_signals: list[SignalTrace]
    nearby_cells: list[str]                     # sigil_ids
    bonded_neighbors: list[str]                 # subset in bonds


class Environment:
    def __init__(self, width: int, height: int, resource_rate: float,
                 resource_range: tuple[float, float] = (5.0, 15.0),
                 deposit_ratio: float = 0.2,
                 deposit_range: tuple[float, float] = (40.0, 80.0)):
        self.width = width
        self.height = height
        self.resource_rate = resource_rate
        self.resource_range = resource_range
        self.deposit_ratio = deposit_ratio
        self.deposit_range = deposit_range
        self.resources: dict[Pos, float] = {}
        self.deposits: dict[Pos, float] = {}  # rich: need 2+ bonded cells
        self.signals: list[SignalTrace] = []

    def spawn_resources(self) -> None:
        for x in range(self.width):
            for y in range(self.height):
                if random.random() < self.resource_rate:
                    pos = (x, y)
                    if random.random() < self.deposit_ratio:
                        amt = random.uniform(*self.deposit_range)
                        self.deposits[pos] = self.deposits.get(pos, 0) + amt
                    else:
                        amt = random.uniform(*self.resource_range)
                        self.resources[pos] = self.resources.get(pos, 0) + amt

    def decay_signals(self) -> None:
        for s in self.signals:
            # Reinforced signals decay slower — traces persist
            # 0 reinforcements: decay 0.90 (~20 ticks)
            # 5+ reinforcements: decay 0.98 (~100+ ticks)
            r = min(s.reinforcements, 5)
            decay = 0.90 + 0.08 * (r / 5)
            s.strength *= decay
            s.age += 1
        self.signals = [s for s in self.signals if s.strength >= 0.1]

    def perceive(self, pos: Pos, radius: int,
                 cell_positions: dict[str, Pos],
                 bonds: set[str]) -> LocalPerception:
        nearby_res = []
        nearby_dep = []
        nearby_sigs = []
        nearby_cells = []
        bonded_near = []

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (pos[0] + dx) % self.width
                ny = (pos[1] + dy) % self.height
                npos = (nx, ny)
                if npos in self.resources:
                    nearby_res.append((npos, self.resources[npos]))
                if npos in self.deposits:
                    nearby_dep.append((npos, self.deposits[npos]))

        for s in self.signals:
            if self._dist(pos, s.position) <= radius:
                nearby_sigs.append(s)

        for sid, cpos in cell_positions.items():
            if self._dist(pos, cpos) <= radius:
                nearby_cells.append(sid)
                if sid in bonds:
                    bonded_near.append(sid)

        return LocalPerception(
            nearby_resources=nearby_res,
            nearby_deposits=nearby_dep,
            nearby_signals=nearby_sigs,
            nearby_cells=nearby_cells,
            bonded_neighbors=bonded_near,
        )

    def consume_resource(self, pos: Pos) -> float:
        amt = self.resources.pop(pos, 0.0)
        return amt

    def consume_deposit(self, pos: Pos) -> float:
        """Rich deposit — caller must verify cooperation requirement."""
        amt = self.deposits.pop(pos, 0.0)
        return amt

    def add_signal(self, pos: Pos, emitter_id: str,
                   kind: str, payload: Pos | None = None,
                   strength: float = 1.0) -> None:
        # Stigmergy: reinforce existing signal with same info nearby
        for s in self.signals:
            if s.kind == kind and s.payload == payload and self._dist(pos, s.position) <= 1:
                s.strength = min(s.strength + strength * 0.5, 5.0)  # cap at 5
                s.reinforcements += 1
                return
        self.signals.append(SignalTrace(
            position=pos, emitter_id=emitter_id,
            kind=kind, payload=payload, strength=strength,
        ))

    def reinforce_at(self, pos: Pos) -> None:
        """Reinforce signals near pos — called when cell uses signal info successfully."""
        for s in self.signals:
            if self._dist(pos, s.position) <= 2:
                s.strength = min(s.strength + 0.3, 5.0)
                s.reinforcements += 1

    def _dist(self, a: Pos, b: Pos) -> int:
        dx = min(abs(a[0] - b[0]), self.width - abs(a[0] - b[0]))
        dy = min(abs(a[1] - b[1]), self.height - abs(a[1] - b[1]))
        return max(dx, dy)  # Chebyshev distance

    def adjacent(self, pos: Pos) -> Pos:
        dx, dy = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1),
                                 (-1, -1), (-1, 1), (1, -1), (1, 1)])
        return ((pos[0] + dx) % self.width, (pos[1] + dy) % self.height)

    def shock_relocate(self) -> None:
        """Clear all resources/deposits, respawn normally (no bonus)."""
        self.resources.clear()
        self.deposits.clear()
        self.spawn_resources()

    def shock_famine(self, duration: int = 50) -> int:
        """Returns tick count for famine end. Caller must track."""
        self.resources.clear()
        self.deposits.clear()
        return duration


# ════════════════════════════════════════════════════════════════
#  Cell — one Sigil Loop
# ════════════════════════════════════════════════════════════════

@dataclass
class Cell:
    sigil_id: str
    energy: float
    psyche: PsycheState
    genome: Genome
    age: int
    position: Pos
    lineage: list[str] = field(default_factory=list)
    lineage_depth: int = 0
    bonds: set[str] = field(default_factory=set)
    brain: str = "rule"       # "rule" | "llm" — inherited on FORK
    alive: bool = True


# ════════════════════════════════════════════════════════════════
#  Action & Decision Engine
# ════════════════════════════════════════════════════════════════

@dataclass
class Action:
    kind: str                # SEARCH | HARVEST | FORK | BOND | SIGNAL | REST
    target: Any = None       # Pos for SEARCH/HARVEST, str for BOND, str for SIGNAL


class DecisionEngine(Protocol):
    def decide(self, cell: Cell, perception: LocalPerception,
               overlay: Overlay) -> Action: ...


class RuleEngine:
    """Genome weights × overlay modulation → softmax sample."""

    def decide(self, cell: Cell, perception: LocalPerception,
               overlay: Overlay) -> Action:
        scores: dict[str, float] = {}
        targets: dict[str, Any] = {}

        # ── Decode incoming signals ──
        # Signals carry real information: locations the cell can't see
        resource_tips: list[Pos] = []  # resource locations from signals
        deposit_tips: list[Pos] = []   # deposit locations from signals
        bond_requests: list[Pos] = []  # cells seeking bonds
        for s in perception.nearby_signals:
            if s.payload is not None:
                if s.kind == "resource":
                    resource_tips.append(s.payload)
                elif s.kind == "deposit":
                    deposit_tips.append(s.payload)
                elif s.kind == "bond":
                    bond_requests.append(s.payload)

        # ── SEARCH (solo foraging) ──
        hunger = max(0.2, (100 - cell.energy) / 100)
        has_tip = bool(resource_tips)
        agency_mod = 0.5 + 0.5 * max(0, overlay.agency)
        scores["SEARCH"] = (hunger + cell.genome.exploration_rate * 0.3
                            + 0.3 * float(has_tip)) * agency_mod

        if perception.nearby_resources:
            best = max(perception.nearby_resources, key=lambda r: r[1])
            targets["SEARCH"] = best[0]
        elif resource_tips:
            # Use signal intel — go to a location we can't see
            targets["SEARCH"] = resource_tips[0]
        else:
            targets["SEARCH"] = None

        # ── HARVEST (cooperative) ──
        # Can be triggered by direct sight OR signal intel
        known_deposits = [d[0] for d in perception.nearby_deposits]
        known_deposits.extend(deposit_tips)
        if known_deposits and (perception.bonded_neighbors or bond_requests):
            targets["HARVEST"] = known_deposits[0]
            coop = cell.genome.cooperation_bias
            scores["HARVEST"] = (hunger + coop * 0.5) * agency_mod * 1.2
        else:
            scores["HARVEST"] = 0.0

        # ── FORK ──
        threshold_energy = cell.genome.fork_threshold * 100
        if cell.energy < threshold_energy or cell.age < 10:
            scores["FORK"] = 0.0
        else:
            maturity = min(cell.age / 50, 1.0)
            scores["FORK"] = maturity * (0.5 + 0.5 * max(0, overlay.agency)) * 0.5

        # ── BOND ──
        unbonded = [c for c in perception.nearby_cells if c not in cell.bonds]
        if not unbonded:
            scores["BOND"] = 0.0
        else:
            warmth = 0.5 + 0.5 * max(0, overlay.valence)
            deposit_pressure = 0.5 if (perception.nearby_deposits or deposit_tips) else 0.0
            scores["BOND"] = (cell.genome.cooperation_bias * warmth + deposit_pressure) * 0.5
            targets["BOND"] = random.choice(unbonded)

        # ── SIGNAL (broadcast real information) ──
        # Score: higher when cell has info worth sharing
        has_resource = bool(perception.nearby_resources)
        has_deposit = bool(perception.nearby_deposits)
        info_value = 0.5 * float(has_deposit) + 0.3 * float(has_resource)
        scores["SIGNAL"] = cell.genome.signal_frequency * (0.1 + info_value) * 0.4
        # Target encodes what to broadcast (kind, payload)
        if has_deposit:
            best_dep = max(perception.nearby_deposits, key=lambda d: d[1])
            targets["SIGNAL"] = ("deposit", best_dep[0])
        elif has_resource:
            best_res = max(perception.nearby_resources, key=lambda r: r[1])
            targets["SIGNAL"] = ("resource", best_res[0])
        else:
            targets["SIGNAL"] = ("bond", cell.position)

        # ── REST ──
        fatigue = 1.0 - cell.energy / 100
        vuln = max(0, overlay.vulnerability)
        scores["REST"] = max(0.05, fatigue * vuln * 0.3)

        # ── Softmax selection ──
        action_kind = self._softmax_sample(scores, cell.genome.risk_tolerance)
        return Action(kind=action_kind, target=targets.get(action_kind))

    @staticmethod
    def _softmax_sample(scores: dict[str, float], risk: float) -> str:
        temperature = 0.1 + risk * 0.9
        keys = list(scores.keys())
        vals = [scores[k] / temperature for k in keys]
        max_v = max(vals) if vals else 0
        exps = [math.exp(v - max_v) for v in vals]
        total = sum(exps)
        if total == 0:
            return random.choice(keys)
        probs = [e / total for e in exps]
        r = random.random()
        cumulative = 0.0
        for k, p in zip(keys, probs):
            cumulative += p
            if r <= cumulative:
                return k
        return keys[-1]


# ════════════════════════════════════════════════════════════════
#  Neural Engine — genome IS the decision function (Phase 7)
# ════════════════════════════════════════════════════════════════

class NeuralEngine:
    """Neural network genome directly maps perception → action scores."""

    ACTIONS = ["SEARCH", "HARVEST", "FORK", "BOND", "SIGNAL", "REST"]

    def decide(self, cell: Cell, perception: LocalPerception,
               overlay: Overlay) -> Action:
        inputs = self._build_inputs(cell, perception, overlay)
        scores = cell.genome.forward(inputs)
        score_dict = dict(zip(self.ACTIONS, scores))

        # Hard constraints — physics can't be overridden
        if cell.energy < 50 or cell.age < 10:
            score_dict["FORK"] = -10.0
        unbonded = [c for c in perception.nearby_cells if c not in cell.bonds]
        if not unbonded:
            score_dict["BOND"] = -10.0
        has_deposits = bool(perception.nearby_deposits)
        has_partners = bool(perception.bonded_neighbors)
        if not has_deposits or not has_partners:
            score_dict["HARVEST"] = -10.0

        action_kind = RuleEngine._softmax_sample(score_dict, 0.3)
        target = self._build_target(action_kind, cell, perception)
        return Action(kind=action_kind, target=target)

    @staticmethod
    def _build_inputs(cell: Cell, perception: LocalPerception,
                      overlay: Overlay) -> list[float]:
        return [
            cell.energy / 100.0,
            min(cell.age, 200) / 200.0,
            min(len(perception.nearby_resources), 5) / 5.0,
            max((r[1] for r in perception.nearby_resources), default=0) / 15.0,
            min(len(perception.nearby_deposits), 3) / 3.0,
            min(len(perception.nearby_cells), 10) / 10.0,
            min(len(perception.bonded_neighbors), 5) / 5.0,
            min(len(perception.nearby_signals), 10) / 10.0,
            overlay.arousal,
            overlay.valence,
            overlay.agency,
            overlay.vulnerability,
            cell.psyche.order / 100.0,
            cell.psyche.flow / 100.0,
            cell.psyche.boundary / 100.0,
            cell.psyche.resonance / 100.0,
        ]

    @staticmethod
    def _build_target(action: str, cell: Cell,
                      perception: LocalPerception) -> Any:
        if action == "SEARCH":
            if perception.nearby_resources:
                return max(perception.nearby_resources, key=lambda r: r[1])[0]
            # Check signal tips
            for s in perception.nearby_signals:
                if s.kind == "resource" and s.payload:
                    return s.payload
            return None
        elif action == "HARVEST":
            if perception.nearby_deposits:
                return perception.nearby_deposits[0][0]
            return None
        elif action == "BOND":
            unbonded = [c for c in perception.nearby_cells if c not in cell.bonds]
            return random.choice(unbonded) if unbonded else None
        elif action == "SIGNAL":
            if perception.nearby_deposits:
                best = max(perception.nearby_deposits, key=lambda d: d[1])
                return ("deposit", best[0])
            elif perception.nearby_resources:
                best = max(perception.nearby_resources, key=lambda r: r[1])
                return ("resource", best[0])
            return ("bond", cell.position)
        return None


# ════════════════════════════════════════════════════════════════
#  LLM Engine — model as "brain chemistry"
# ════════════════════════════════════════════════════════════════

VALID_ACTIONS = {"SEARCH", "HARVEST", "FORK", "BOND", "SIGNAL", "REST"}

# Strip ```json ... ``` wrappers
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LLMEngine:
    """LLM replaces the rule engine. Genome/psyche/perception → prompt → action."""

    def __init__(
        self,
        config: LLMConfig,
        fallback: RuleEngine | None = None,
        urlopen_fn: Any | None = None,
    ):
        self.config = config
        self.transport = get_transport_adapter(config.transport)
        self.fallback = fallback or RuleEngine()
        self._pool = ThreadPoolExecutor(max_workers=config.max_workers)
        self._urlopen = urlopen_fn or urllib.request.urlopen
        self._stats = {"calls": 0, "fallbacks": 0, "errors": 0}

    # ── Single-cell prompt ──

    @staticmethod
    def _build_prompt(cell: Cell, perception: LocalPerception,
                      overlay: Overlay) -> str:
        res = [(p, int(a)) for p, a in perception.nearby_resources[:3]]
        dep = [(p, int(a)) for p, a in perception.nearby_deposits[:2]]
        sigs = [f"{s.kind}@{s.payload}" for s in perception.nearby_signals[:3]
                if s.payload]
        neighbors = len(perception.nearby_cells)
        bonded = len(perception.bonded_neighbors)

        # Compact prompt — state + rules + format, no fluff
        return (
            f"Cell. energy={cell.energy:.0f} age={cell.age} "
            f"psyche:O={cell.psyche.order:.0f}/F={cell.psyche.flow:.0f}/"
            f"B={cell.psyche.boundary:.0f}/R={cell.psyche.resonance:.0f} "
            f"genome:fork_thr={cell.genome.fork_threshold:.2f} "
            f"coop={cell.genome.cooperation_bias:.2f} apt={cell.genome.aptitude:.2f}\n"
            f"See: res={res} dep={dep} sigs=[{','.join(sigs)}] "
            f"cells={neighbors} bonded={bonded}\n"
            f"SEARCH=find food(cost 1) | HARVEST=coop dig deposit(need bond partner near deposit) "
            f"| FORK=reproduce(need energy>{cell.genome.fork_threshold*100:.0f},costs 55%,child inherits mutated genome) "
            f"| BOND=ally neighbor | SIGNAL=broadcast | REST=recover\n"
            f"Goal: maximize descendants. Energy hoarding=genetic dead end. "
            f"FORK when able, BOND to unlock HARVEST, SIGNAL to help allies.\n"
            f'JSON only: {{"action":"...","target":[x,y]}}'
        )

    # ── Parse LLM response ──

    @staticmethod
    def _parse_response(text: str, perception: LocalPerception,
                        cell: Cell) -> Action | None:
        # Strip markdown code blocks
        m = _JSON_BLOCK.search(text)
        raw = m.group(1) if m else text.strip()
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            return None
        action = d.get("action", "").upper()
        if action not in VALID_ACTIONS:
            return None

        target = d.get("target")
        # Convert target list to tuple
        if isinstance(target, list) and len(target) == 2 and target[0] is not None and target[1] is not None:
            try:
                target = (int(target[0]), int(target[1]))
            except (ValueError, TypeError):
                target = None
        else:
            target = None

        # Wire up targets to match what _execute expects
        if action == "BOND":
            unbonded = [c for c in perception.nearby_cells if c not in cell.bonds]
            target = random.choice(unbonded) if unbonded else None
        elif action == "SIGNAL":
            if perception.nearby_deposits:
                best = max(perception.nearby_deposits, key=lambda d: d[1])
                target = ("deposit", best[0])
            elif perception.nearby_resources:
                best = max(perception.nearby_resources, key=lambda r: r[1])
                target = ("resource", best[0])
            else:
                target = ("bond", cell.position)
        elif action == "HARVEST":
            known = [d[0] for d in perception.nearby_deposits]
            target = known[0] if known else target

        return Action(kind=action, target=target)

    # ── API call ──

    def _call_api(self, prompt: str) -> str | None:
        try:
            req = self.transport.build_request(self.config, prompt)
            resp = self._urlopen(req, timeout=15)
            payload = json.loads(resp.read())
            return self.transport.parse_response(payload)
        except Exception:
            self._stats["errors"] += 1
            return None

    # ── Single decide (called per cell) ──

    def decide(self, cell: Cell, perception: LocalPerception,
               overlay: Overlay) -> Action:
        self._stats["calls"] += 1
        prompt = self._build_prompt(cell, perception, overlay)
        text = self._call_api(prompt)
        if text:
            action = self._parse_response(text, perception, cell)
            if action:
                return action
        # Fallback to rule engine
        self._stats["fallbacks"] += 1
        return self.fallback.decide(cell, perception, overlay)

    # ── Batch decide (all cells in one tick, concurrent) ──

    def decide_batch(self, cells_data: list[tuple[Cell, LocalPerception, Overlay]]
                     ) -> list[Action]:
        results: list[Action | None] = [None] * len(cells_data)
        futures = {}
        for i, (cell, perc, ovl) in enumerate(cells_data):
            prompt = self._build_prompt(cell, perc, ovl)
            fut = self._pool.submit(self._call_api, prompt)
            futures[fut] = (i, cell, perc, ovl)

        for fut in as_completed(futures):
            i, cell, perc, ovl = futures[fut]
            self._stats["calls"] += 1
            text = fut.result()
            if text:
                action = self._parse_response(text, perc, cell)
                if action:
                    results[i] = action
                    continue
            # Fallback
            self._stats["fallbacks"] += 1
            results[i] = self.fallback.decide(cell, perc, ovl)

        return results  # type: ignore

    def print_stats(self) -> None:
        c, f, e = self._stats["calls"], self._stats["fallbacks"], self._stats["errors"]
        pct = f / c * 100 if c else 0
        print(f"  LLM stats: {c} calls, {f} fallbacks ({pct:.1f}%), {e} errors")

    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def close(self) -> None:
        self._pool.shutdown(wait=True)


# ════════════════════════════════════════════════════════════════
#  Observer — metrics collection
# ════════════════════════════════════════════════════════════════

def _shannon_entropy(values: list[float], bins: int = 10,
                     lo: float = 0.0, hi: float = 1.0) -> float:
    """Shannon entropy of a distribution via histogram binning."""
    if not values:
        return 0.0
    counts = [0] * bins
    bw = (hi - lo) / bins
    for v in values:
        idx = min(int((v - lo) / bw), bins - 1)
        counts[idx] += 1
    n = len(values)
    ent = 0.0
    for c in counts:
        if c > 0:
            p = c / n
            ent -= p * math.log2(p)
    return ent


def _action_entropy(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    ent = 0.0
    for c in counts.values():
        if c > 0:
            p = c / total
            ent -= p * math.log2(p)
    return ent


@dataclass
class TickSnapshot:
    tick: int
    population: int
    total_energy: float
    avg_age: float
    max_age: int
    total_bonds: int
    max_lineage_depth: int
    genome_mean: list[float]
    genome_std: list[float]
    psyche_mean: list[float]
    action_counts: dict[str, int]
    births: int
    deaths: int
    brain_counts: dict[str, int] = field(default_factory=dict)
    total_signals: int = 0
    traces: int = 0
    max_reinforcement: int = 0
    genome_entropy: list[float] = field(default_factory=list)  # per-gene Shannon entropy
    action_entropy: float = 0.0


class Observer:
    def __init__(self) -> None:
        self.history: list[TickSnapshot] = []

    def record(self, tick: int, cells: dict[str, Cell],
               births: int, deaths: int,
               action_counts: dict[str, int],
               signals: list[SignalTrace] | None = None) -> None:
        sig_total = len(signals) if signals else 0
        sig_traces = sum(1 for s in signals if s.reinforcements > 0) if signals else 0
        sig_max_r = max((s.reinforcements for s in signals), default=0) if signals else 0

        if not cells:
            self.history.append(TickSnapshot(
                tick=tick, population=0, total_energy=0, avg_age=0,
                max_age=0, total_bonds=0, max_lineage_depth=0,
                genome_mean=[0]*6, genome_std=[0]*6, psyche_mean=[0]*4,
                action_counts=action_counts, births=births, deaths=deaths,
                total_signals=sig_total, traces=sig_traces,
                max_reinforcement=sig_max_r,
            ))
            return

        alive = list(cells.values())
        ages = [c.age for c in alive]
        genomes = [c.genome.weights() for c in alive]
        psyches = [c.psyche.values() for c in alive]
        n = len(alive)

        ng = len(genomes[0])  # 6 genes
        g_mean = [sum(g[i] for g in genomes) / n for i in range(ng)]
        g_std = [math.sqrt(sum((g[i] - g_mean[i])**2 for g in genomes) / n) for i in range(ng)]
        p_mean = [sum(p[i] for p in psyches) / n for i in range(4)]

        bond_count = sum(len(c.bonds) for c in alive) // 2
        max_lin = max((c.lineage_depth for c in alive), default=0)

        brain_counts: dict[str, int] = {}
        for c in alive:
            brain_counts[c.brain] = brain_counts.get(c.brain, 0) + 1

        # Entropy: per-gene genome diversity + action diversity
        if ng <= 10:  # classic 6-float genome
            gene_ranges = [(0.3, 0.9), (0, 1), (0, 1), (0, 1), (0, 1), (0, 1)]
            g_entropy = [
                _shannon_entropy([g[i] for g in genomes], lo=gene_ranges[i][0], hi=gene_ranges[i][1])
                for i in range(ng)
            ]
        else:  # neural genome — aggregate entropy (sample 6 representative weights)
            indices = [0, ng // 5, ng * 2 // 5, ng * 3 // 5, ng * 4 // 5, ng - 1]
            g_entropy = [
                _shannon_entropy([g[i] for g in genomes], lo=-3.0, hi=3.0)
                for i in indices
            ]
        a_entropy = _action_entropy(action_counts)

        self.history.append(TickSnapshot(
            tick=tick,
            population=n,
            total_energy=sum(c.energy for c in alive),
            avg_age=sum(ages) / n,
            max_age=max(ages),
            total_bonds=bond_count,
            max_lineage_depth=max_lin,
            genome_mean=g_mean,
            genome_std=g_std,
            psyche_mean=p_mean,
            action_counts=action_counts,
            births=births,
            deaths=deaths,
            brain_counts=brain_counts,
            total_signals=sig_total,
            traces=sig_traces,
            max_reinforcement=sig_max_r,
            genome_entropy=g_entropy,
            action_entropy=a_entropy,
        ))

    def print_tick(self, snap: TickSnapshot) -> None:
        gm = snap.genome_mean
        gs = snap.genome_std
        pm = snap.psyche_mean
        acts = snap.action_counts
        total_acts = sum(acts.values()) or 1

        print(f"\n── tick {snap.tick:>5d} ──────────────────────────────────────")
        brain_str = ""
        if snap.brain_counts and len(snap.brain_counts) > 1:
            parts = [f"{k}={v}" for k, v in sorted(snap.brain_counts.items())]
            brain_str = f"  [{' '.join(parts)}]"
        print(f"  pop: {snap.population:>4d}  |  +{snap.births} -{snap.deaths}  |  "
              f"energy: {snap.total_energy:>7.0f}  |  bonds: {snap.total_bonds}{brain_str}")
        trace_str = ""
        if snap.total_signals > 0:
            trace_str = f"  |  signals: {snap.total_signals} traces: {snap.traces} max_r: {snap.max_reinforcement}"
        print(f"  age: avg={snap.avg_age:>5.1f}  max={snap.max_age:>5d}  |  "
              f"lineage depth: {snap.max_lineage_depth}{trace_str}")
        if len(gm) <= 10:
            print(f"  genome μ: fork={gm[0]:.2f} expl={gm[1]:.2f} coop={gm[2]:.2f} "
                  f"sig={gm[3]:.2f} risk={gm[4]:.2f} apt={gm[5]:.2f}")
            print(f"  genome σ: fork={gs[0]:.3f} expl={gs[1]:.3f} coop={gs[2]:.3f} "
                  f"sig={gs[3]:.3f} risk={gs[4]:.3f} apt={gs[5]:.3f}")
        else:
            total_sigma = sum(gs)
            avg_abs = sum(abs(v) for v in gm) / len(gm)
            print(f"  neural genome ({len(gm)} weights): |w|_avg={avg_abs:.3f}  σ_total={total_sigma:.3f}")
        print(f"  psyche μ: order={pm[0]:.1f} flow={pm[1]:.1f} "
              f"boundary={pm[2]:.1f} resonance={pm[3]:.1f}")
        print(f"  actions:  ", end="")
        for a in ["SEARCH", "HARVEST", "FORK", "BOND", "SIGNAL", "REST"]:
            c = acts.get(a, 0)
            print(f"{a}={c}({c/total_acts:.0%}) ", end="")
        print()
        if snap.genome_entropy:
            ge = snap.genome_entropy
            print(f"  entropy:  genome=[{' '.join(f'{e:.2f}' for e in ge)}] "
                  f"action={snap.action_entropy:.2f}")

    def print_report(self) -> None:
        if not self.history:
            print("No data.")
            return
        first = self.history[0]
        last = self.history[-1]
        print("\n" + "=" * 60)
        print("  SIMULATION REPORT")
        print("=" * 60)
        print(f"  Ticks: {last.tick}")
        print(f"  Population: {first.population} → {last.population}")
        print(f"  Max age reached: {max(s.max_age for s in self.history)}")
        print(f"  Max bonds: {max(s.total_bonds for s in self.history)}")
        print(f"  Max lineage depth: {max(s.max_lineage_depth for s in self.history)}")

        # Genome convergence
        if len(self.history) >= 2:
            first_std = sum(self.history[0].genome_std)
            last_std = sum(last.genome_std)
            direction = "converging" if last_std < first_std else "diverging"
            print(f"  Genome σ: {first_std:.3f} → {last_std:.3f} ({direction})")

        # Dominant strategy
        gm = last.genome_mean
        if len(gm) <= 10:
            labels = ["fork_threshold", "exploration", "cooperation", "signaling", "risk", "aptitude"]
            print(f"\n  Final genome (avg):")
            for label, val in zip(labels, gm):
                bar = "█" * int(val * 20)
                print(f"    {label:>15s}: {val:.3f} {bar}")
        else:
            print(f"\n  Neural genome ({len(gm)} weights):")
            avg_abs = sum(abs(v) for v in gm) / len(gm)
            max_abs = max(abs(v) for v in gm)
            print(f"    |w|_avg: {avg_abs:.4f}  |w|_max: {max_abs:.4f}")

        print(f"\n  Final psyche (avg):")
        pm = last.psyche_mean
        for label, val in zip(["order", "flow", "boundary", "resonance"], pm):
            print(f"    {label:>10s}: {val:.1f}")

        # Total births/deaths
        total_births = sum(s.births for s in self.history)
        total_deaths = sum(s.deaths for s in self.history)
        print(f"\n  Total births: {total_births}  |  Total deaths: {total_deaths}")
        print("=" * 60)

    def save(self, path: Path) -> None:
        data = [asdict(s) for s in self.history]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"\n  History saved to {path}")


# ════════════════════════════════════════════════════════════════
#  Simulation — the primordial soup itself
# ════════════════════════════════════════════════════════════════

@dataclass
class SimConfig:
    width: int = 30
    height: int = 30
    resource_rate: float = 0.02
    resource_range: tuple[float, float] = (5.0, 15.0)
    initial_population: int = 50
    initial_energy: float = 100.0
    mutation_sigma: float = 0.05
    perception_radius: int = 3
    ticks: int = 1000
    print_every: int = 50
    seed: int = 42
    data_dir: str = "data"
    mode_name: str = "rule"
    output_name: str | None = None
    ablate_psyche: bool = False  # fix Psyche at baseline (50,50,50,50)


class Simulation:
    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.env = Environment(
            config.width, config.height,
            config.resource_rate, config.resource_range,
        )
        self.rule_engine = RuleEngine()
        self.neural_engine = NeuralEngine()
        self.llm_engine: LLMEngine | None = None  # set externally for hybrid/llm mode
        self.observer = Observer()
        self.cells: dict[str, Cell] = {}
        self.tick_count = 0
        self._id_counter = 0
        self.shocks: dict[int, str] = {}  # tick → shock type
        self._famine_until: int = 0       # suppress spawning until this tick

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"SIG_{self._id_counter:06d}"

    def seed(self, n: int, brain: str = "rule") -> None:
        """Create initial population with random genomes at random positions."""
        for _ in range(n):
            sid = self._next_id()
            genome = NeuralGenome.random() if brain == "neural" else Genome.random()
            self.cells[sid] = Cell(
                sigil_id=sid,
                energy=self.config.initial_energy,
                psyche=PsycheState(),
                genome=genome,
                age=0,
                position=(random.randint(0, self.config.width - 1),
                          random.randint(0, self.config.height - 1)),
                brain=brain,
            )

    def _prepare_cell(self, cell: Cell,
                      cell_positions: dict[str, Pos]
                      ) -> tuple[Cell, LocalPerception, Overlay] | None:
        """Metabolism + psyche + perception for one cell. Returns None if dead."""
        cell.energy -= 1
        if cell.energy <= 0:
            cell.alive = False
            return None

        if self.config.ablate_psyche:
            # Fix Psyche at baseline — overlay = neutral
            cell.psyche = PsycheState()
        else:
            apply_decay(cell.psyche)
            apply_coupling(cell.psyche)

        bond_radius = self.config.perception_radius
        for bid in list(cell.bonds):
            if bid not in self.cells or not self.cells[bid].alive:
                cell.bonds.discard(bid)
                continue
            if self.env._dist(cell.position, self.cells[bid].position) <= self.config.perception_radius:
                bond_radius = self.config.perception_radius + 2
                break

        perception = self.env.perceive(
            cell.position, bond_radius, cell_positions, cell.bonds,
        )
        perception.nearby_cells = [c for c in perception.nearby_cells if c != cell.sigil_id]
        overlay = compute_overlay(cell.psyche)
        return cell, perception, overlay

    def tick(self) -> None:
        if self.tick_count < self._famine_until:
            pass  # no resources during famine
        else:
            self.env.spawn_resources()
        self.env.decay_signals()

        cell_positions = {sid: c.position for sid, c in self.cells.items() if c.alive}

        order = list(self.cells.values())
        random.shuffle(order)

        births: list[Cell] = []
        deaths: list[str] = []
        action_counts: dict[str, int] = {}

        # ── Phase A: prepare all living cells ──
        rule_prepared: list[tuple[Cell, LocalPerception, Overlay]] = []
        neural_prepared: list[tuple[Cell, LocalPerception, Overlay]] = []
        llm_prepared: list[tuple[Cell, LocalPerception, Overlay]] = []

        for cell in order:
            if not cell.alive:
                continue
            result = self._prepare_cell(cell, cell_positions)
            if result is None:
                deaths.append(cell.sigil_id)
            elif cell.brain == "llm" and self.llm_engine:
                llm_prepared.append(result)
            elif cell.brain == "neural":
                neural_prepared.append(result)
            else:
                rule_prepared.append(result)

        # ── Phase B: LLM batch (concurrent API calls) ──
        if llm_prepared and self.llm_engine:
            llm_actions = self.llm_engine.decide_batch(llm_prepared)
            for (cell, perc, ovl), action in zip(llm_prepared, llm_actions):
                action_counts[action.kind] = action_counts.get(action.kind, 0) + 1
                stimulus_key = self._execute(cell, action, births)
                if not self.config.ablate_psyche:
                    apply_stimulus(cell.psyche, stimulus_key)
                cell.age += 1

        # ── Phase B2: NeuralEngine (sequential, fast) ──
        for cell, perception, overlay in neural_prepared:
            action = self.neural_engine.decide(cell, perception, overlay)
            action_counts[action.kind] = action_counts.get(action.kind, 0) + 1
            stimulus_key = self._execute(cell, action, births)
            if not self.config.ablate_psyche:
                apply_stimulus(cell.psyche, stimulus_key)
            cell.age += 1

        # ── Phase C: RuleEngine (sequential, fast) ──
        for cell, perception, overlay in rule_prepared:
            action = self.rule_engine.decide(cell, perception, overlay)
            action_counts[action.kind] = action_counts.get(action.kind, 0) + 1
            stimulus_key = self._execute(cell, action, births)
            if not self.config.ablate_psyche:
                apply_stimulus(cell.psyche, stimulus_key)
            cell.age += 1

        # Apply births and deaths
        for child in births:
            self.cells[child.sigil_id] = child
            cell_positions[child.sigil_id] = child.position

        for sid in deaths:
            dead = self.cells[sid]
            for bid in dead.bonds:
                if bid in self.cells:
                    self.cells[bid].bonds.discard(sid)
            del self.cells[sid]
            cell_positions.pop(sid, None)

        self.tick_count += 1
        self.observer.record(self.tick_count, self.cells,
                             len(births), len(deaths), action_counts,
                             self.env.signals)

    def _execute(self, cell: Cell, action: Action, births: list[Cell]) -> str:
        """Execute action, return stimulus key for psyche update."""
        # Neural genomes don't have named genes — use neutral defaults
        apt = getattr(cell.genome, 'aptitude', 0.5)

        if action.kind == "SEARCH":
            # Hunters (high aptitude) search cheaper
            cost = 1.0 if apt >= 0.5 else 1.5
            cell.energy -= cost
            target = action.target
            if target is not None:
                if target in self.env.resources:
                    cell.position = target
                    gained = self.env.consume_resource(target)
                    gained *= (0.8 + 0.4 * apt)
                    cell.energy += gained
                    self.env.reinforce_at(target)  # stigmergy: success reinforces nearby signals
                    return "SEARCH_OK"
                else:
                    cell.position = self._step_toward(cell.position, target)
                    gained = self.env.consume_resource(cell.position)
                    if gained > 0:
                        gained *= (0.8 + 0.4 * apt)
                        cell.energy += gained
                        self.env.reinforce_at(cell.position)
                        return "SEARCH_OK"
                    return "SEARCH_FAIL"
            else:
                cell.position = self.env.adjacent(cell.position)
                gained = self.env.consume_resource(cell.position)
                if gained > 0:
                    gained *= (0.8 + 0.4 * apt)
                    cell.energy += gained
                    return "SEARCH_OK"
                return "SEARCH_FAIL"

        elif action.kind == "HARVEST":
            cell.energy -= 1
            target = action.target
            if target and target in self.env.deposits:
                cell.position = target
                # Check: is a bonded cell within radius 1 of the deposit?
                has_partner = False
                for bid in cell.bonds:
                    if bid in self.cells and self.cells[bid].alive:
                        if self.env._dist(self.cells[bid].position, target) <= 1:
                            has_partner = True
                            break
                if has_partner:
                    gained = self.env.consume_deposit(target)
                    share = gained / 2
                    cell.energy += share
                    for bid in cell.bonds:
                        if bid in self.cells and self.cells[bid].alive:
                            if self.env._dist(self.cells[bid].position, target) <= 1:
                                self.cells[bid].energy += share
                                break
                    self.env.reinforce_at(target)  # stigmergy: deposit success
                    return "HARVEST_OK"
                else:
                    return "HARVEST_FAIL"
            else:
                if target:
                    cell.position = self._step_toward(cell.position, target)
                else:
                    cell.position = self.env.adjacent(cell.position)
                return "HARVEST_FAIL"

        elif action.kind == "FORK":
            child_energy = cell.energy * 0.45
            cell.energy *= 0.45  # 10% entropy loss
            child_depth = cell.lineage_depth + 1
            child = Cell(
                sigil_id=self._next_id(),
                energy=child_energy,
                psyche=PsycheState(),
                genome=cell.genome.mutate(self.config.mutation_sigma),
                age=0,
                position=self.env.adjacent(cell.position),
                lineage=(cell.lineage + [cell.sigil_id])[-20:],
                lineage_depth=child_depth,
                brain=cell.brain,
            )
            births.append(child)
            return "FORK"

        elif action.kind == "BOND":
            target_id = action.target
            if target_id and target_id in self.cells and self.cells[target_id].alive:
                cell.bonds.add(target_id)
                self.cells[target_id].bonds.add(cell.sigil_id)
            return "BOND"

        elif action.kind == "SIGNAL":
            # Scouts (low aptitude) emit stronger signals — last longer, visible further
            signal_power = 1.0 + (1.0 - apt)  # range [1.0, 2.0]
            if isinstance(action.target, tuple) and len(action.target) == 2:
                kind, payload = action.target
                self.env.add_signal(cell.position, cell.sigil_id,
                                    kind=kind, payload=payload,
                                    strength=signal_power)
            else:
                self.env.add_signal(cell.position, cell.sigil_id,
                                    kind="bond", payload=cell.position,
                                    strength=signal_power)
            return "SIGNAL"

        else:  # REST
            return "REST"

    def _step_toward(self, current: Pos, target: Pos) -> Pos:
        """Move one step toward target on toroidal grid."""
        cx, cy = current
        tx, ty = target

        dx = tx - cx
        if abs(dx) > self.env.width // 2:
            dx = -dx // abs(dx) if dx != 0 else 0
        else:
            dx = 1 if dx > 0 else (-1 if dx < 0 else 0)

        dy = ty - cy
        if abs(dy) > self.env.height // 2:
            dy = -dy // abs(dy) if dy != 0 else 0
        else:
            dy = 1 if dy > 0 else (-1 if dy < 0 else 0)

        return ((cx + dx) % self.env.width, (cy + dy) % self.env.height)

    def run(self) -> None:
        mode = self.config.mode_name
        model_info = ""
        if self.llm_engine:
            model_info = (
                f", profile={self.llm_engine.config.profile_id}"
                f", transport={self.llm_engine.config.transport}"
                f", model={self.llm_engine.config.model}"
            )
        print(f"Primordial Soup — {self.config.initial_population} cells, "
              f"{self.config.width}x{self.config.height} grid, "
              f"seed={self.config.seed}, mode={mode}{model_info}")
        print(f"Running {self.config.ticks} ticks...")

        random.seed(self.config.seed)
        # In hybrid mode, seed() is called externally with brain tags
        if not self.cells:
            self.seed(self.config.initial_population)
        try:
            for t in range(self.config.ticks):
                # Environmental shocks
                tick_num = t + 1
                if tick_num in self.shocks:
                    shock = self.shocks[tick_num]
                    if shock == "relocate":
                        print(f"\n  *** SHOCK at tick {tick_num}: resources relocated ***")
                        self.env.shock_relocate()
                    elif shock == "famine":
                        dur = 50
                        self._famine_until = tick_num + dur
                        self.env.resources.clear()
                        self.env.deposits.clear()
                        print(f"\n  *** SHOCK at tick {tick_num}: FAMINE for {dur} ticks (no spawning until {self._famine_until}) ***")
                    elif shock == "wipe_traces":
                        print(f"\n  *** SHOCK at tick {tick_num}: all traces wiped ***")
                        self.env.signals.clear()
                    elif shock == "famine+wipe":
                        dur = 50
                        self._famine_until = tick_num + dur
                        self.env.resources.clear()
                        self.env.deposits.clear()
                        self.env.signals.clear()
                        print(f"\n  *** SHOCK at tick {tick_num}: FAMINE + TRACES WIPED ***")

                self.tick()

                if self.observer.history and t % self.config.print_every == 0:
                    self.observer.print_tick(self.observer.history[-1])

                if not self.cells:
                    print(f"\n  *** EXTINCTION at tick {self.tick_count} ***")
                    break

            # Final report
            if self.observer.history:
                self.observer.print_tick(self.observer.history[-1])
            self.observer.print_report()
            if self.llm_engine:
                self.llm_engine.print_stats()

            # Save history
            data_dir = Path(self.config.data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            output_name = self.config.output_name or f"run_{mode}_seed{self.config.seed}.json"
            self.observer.save(data_dir / output_name)
        finally:
            if self.llm_engine:
                self.llm_engine.close()
