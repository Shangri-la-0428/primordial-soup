# Primordial Soup — Lab Report

> Goal: validate that intelligent organization can be **evolved**, not designed.
> Core thesis: Seed + Time + Selection Pressure = Emergence

---

## Phase 1: Rule Engine Foundation

**Date**: 2026-04-08
**Config**: 50 cells, 30x30 grid, 1000 ticks, seed=42

### Genome (6 genes)
fork_threshold, exploration_rate, cooperation_bias, signal_frequency, risk_tolerance, aptitude

### Key Results (3 seeds: 42, 7, 123)

| Metric | Value |
|--------|-------|
| Carrying capacity | ~200 cells (emerges naturally) |
| Convergent strategy | fork=0.72, coop=0.75, risk=0.04, apt=0.64 |
| Genome sigma | 1.6 → 0.9~1.2 (selection works) |
| Max age | 780-836 ticks |
| Lineage depth | 16-18 generations |

### Emergent Phenomena
- **K-strategy**: high cooperation, long lifespan, conservative reproduction
- **Role differentiation**: aptitude gene maintains diversity (hunter/scout axis)
- **Information economics**: signals carry real location data, cooperation gene dropped from 0.94 to 0.67 when signals became informative (selective cooperation)
- **Risk → 0**: cells evolved near-deterministic (greedy) decisions

### Conclusion
Foundation solid. Resource scarcity creates carrying capacity. Evolution converges across seeds. Cooperation and specialization emerge without design.

---

## Phase 2: Bug Fixes & Audit

**Date**: 2026-04-08

### Fixes Applied
1. **Lineage memory cap**: added `lineage_depth` counter, list capped at 20 entries
2. **HARVEST consistency**: stale signal targets now step-toward (matching SEARCH behavior)
3. **Target parse safety**: LLM returning `[null, null]` no longer crashes

### Audit Passed
- Toroidal math correct
- Psyche decay/coupling ported correctly from chemistry.ts
- Bond cleanup handles mutual death within same tick
- No energy leaks, no data written outside project dir

---

## Phase 3: LLM Brain Chemistry

**Date**: 2026-04-09
**API**: Tencent LKeap, kimi-k2.5, ~2.3s/call, 10+ concurrent OK
**Config**: 20 cells, 100 ticks

### LLM-Only Results

| Metric | RuleEngine | LLM (kimi-k2.5) |
|--------|-----------|------------------|
| FORK % | 3% | **43%** |
| Cooperation gene | 0.75 | **0.07** |
| Fork threshold | 0.72 | **0.43** |
| Risk tolerance | 0.04 | **0.71** |
| Avg lifespan | ~100 ticks | **5.9 ticks** |
| Lineage depth (100t) | ~8 | **23** |
| HARVEST % | 37% | **0%** |
| Strategy | K (long-lived cooperator) | **r (fast reproducer)** |

### Key Insight
Same genome, same environment, different decision function → completely different ecology. The "brain chemistry" (how state maps to action) determines which evolutionary strategy emerges. LLM produced ultraconservative-then-explosive r-strategy. Rule engine produced cooperative K-strategy.

**LLM stats**: 7,756 calls, 32 fallbacks (0.4%) — parsing reliable.

---

## Phase 4: Hybrid Competition

**Date**: 2026-04-09
**Config**: 10 rule + 10 llm cells, 100 ticks, same environment

### Population Trajectory

```
tick  1:  llm=17  rule=12   ← LLM explodes first (FORK frenzy)
tick 11:  llm=92  rule=29   ← LLM peaks at 3:1 ratio
tick 21:  llm=93  rule=61   ← Rule catching up
tick 31:  llm=64  rule=69   ← CROSSOVER — Rule overtakes
tick 41:  llm=63  rule=105  ← Rule pulling ahead
tick 61:  llm=19  rule=129  ← LLM collapsing
tick 81:  llm=25  rule=148  ← brief LLM bounce
tick100:  llm=8   rule=217  ← Rule wins 27:1
```

### Evolutionary Narrative
1. **Tick 1-10**: LLM r-strategy (aggressive FORK) creates population explosion. 3x Rule cells.
2. **Tick 10-30**: Resources depleted by LLM swarm. LLM avg lifespan ~5 ticks. Massive churn.
3. **Tick 30**: **Crossover point.** Rule cells, with cooperation (HARVEST 15%→26%) and longer lifespans (avg 17 ticks), surpass LLM.
4. **Tick 30-100**: Rule dominance accelerates. Bond networks grow (452 bonds). LLM cells can't sustain — they FORK into starvation.
5. **Tick 100**: LLM reduced to 8 remnants (3.6%). Rule controls 96.4%.

### Conclusion
**K-strategy (cooperate, conserve, bond) beats r-strategy (reproduce, die, repeat) under resource scarcity.** Consistent with ecological theory. The "brain" that wins is the one whose decision mapping aligns with environmental carrying capacity — not the one that reproduces fastest.

LLM cost: 3,406 API calls, 6 fallbacks (0.2%).

---

## Next: Phase 5 — Persistent Traces (Thronglets Projection)

**Hypothesis**: Adding reinforceable environmental signals (Traces) will enable collective memory and self-organizing spatial structures — the embryonic form of culture.

**Design**:
- Signals reinforced by multiple cells resist decay → become Traces
- Traces = public knowledge (no owner)
- Used traces strengthen, neglected traces fade
- Zero LLM cost, pure rule engine

**What to observe**:
- Do stable "paths" to resources emerge?
- Do "territories" form around deposit clusters?
- Does trace-awareness create a new selection axis?
- Does collective memory accelerate or change genome convergence?

### Results (500 ticks, seed=42)

**Trace formation**:
```
tick   1: signals=13   traces=0    max_reinforcement=0
tick  51: signals=715  traces=684  max_reinforcement=37
tick 101: signals=1281 traces=1260 max_reinforcement=62
tick 201: signals=2075 traces=2056 max_reinforcement=116
tick 500: signals=3594 traces=3584 max_reinforcement=286
```

99.7% of signals become traces. max_reinforcement=286 means the most popular signal was reinforced 286 times — a well-worn "path" that persisted the entire simulation.

**Genome shift (Phase 1 baseline → Phase 5 with traces)**:

| Gene | Phase 1 (no traces) | Phase 5 (traces) | Change |
|------|--------------------|--------------------|--------|
| signaling | 0.37 | **0.72** | +95% — signals now pay off via trace persistence |
| risk | 0.04 | **0.08** | same direction, still near-deterministic |
| cooperation | 0.75 | **0.62** | -17% — traces reduce need for direct cooperation? |
| aptitude | 0.64 | **0.75** | +17% — hunter specialization deepened |
| HARVEST % | 37% | **38%** | stable |
| SIGNAL % | ~3% | **1-10%** (variable) | signaling gene high even when action % is low |

**Key Insights**:
1. **Signaling gene nearly doubled** (0.37 → 0.72). Traces make signaling a fitness advantage — your signals persist and help your descendants find resources. Evolution selected for this.
2. **Cooperation slightly decreased** (0.75 → 0.62). Traces create a form of indirect cooperation (stigmergy) that partially substitutes direct bonding. Collective memory reduces dependence on individual bonds.
3. **3,594 signals in environment at tick 500** — the soup has a rich information layer. 99.7% are traces (reinforced at least once). This is an emergent knowledge commons.
4. **max_reinforcement=286** — some locations are "well-known" to the entire population. This is proto-culture: information that persists beyond any individual's lifespan.

**Conclusion**: Traces create a new evolutionary axis. Signaling is no longer altruistic — it's self-interested because your signals become persistent landmarks that benefit your lineage. This is the embryonic form of niche construction: organisms modifying their environment in ways that feed back into their own evolution.

---

---

## Phase 5b: Environmental Shock — Famine Test

**Date**: 2026-04-09
**Design**: 50 ticks of no resource spawning at tick 500. Two conditions:
- **A**: Famine only (traces intact)
- **B**: Famine + all traces wiped

### Results

```
             A: FAMINE (traces intact)    B: FAMINE + TRACES WIPED
tick 476:    pop=201  energy=7995          pop=199  energy=8338
── SHOCK at tick 500 ──
tick 501:    pop=206  energy=6314          pop=199  energy=6002
tick 526:    pop=33   energy=724           pop=28   energy=426
tick 549:    —                             *** EXTINCTION ***
tick 551:    pop=5    energy=116           (dead)
tick 576:    pop=5    energy=244           (dead)
tick 601:    pop=12   energy=1829          (dead)
tick 651:    pop=49   energy=9819          (dead)
tick 700:    pop=222  energy=33196         (dead)
```

### Analysis

**Famine is brutal**: both groups crash from ~200 to ~30 in 25 ticks. Without new food, metabolism (1/tick) + action costs drain cells faster than old resources sustain them.

**Traces are the difference between life and death**:
- **With traces**: 5 survivors at the nadir (tick 551). They cling to life, and when food returns at tick 550, they recover. By tick 700 the population is back to 222 — **full recovery in 150 ticks**.
- **Without traces**: EXTINCT at tick 549. Same famine, same genomes, same starting population. The only difference: no collective memory to guide the last survivors to remaining food.

**Why traces save lives during famine**:
1. During the 50-tick famine, scattered residual resources exist (deposits that weren't consumed before the shock)
2. Traces point to their locations — cells with traces can find these scraps
3. Without traces, cells search blind. In a depleted environment, blind search = death
4. The last 5 survivors in condition A were likely the ones near high-reinforcement traces pointing to unconsumed deposits

**Recovery dynamics (condition A)**:
- Tick 551: food returns, 5 survivors with high cooperation genome begin rebuilding
- Tick 601: 12 cells — slow start, establishing new bond networks
- Tick 651: 49 cells — exponential growth phase
- Tick 700: 222 cells — exceeded pre-shock levels. Energy=33,196 (4x pre-shock) because 150 ticks of uncollected resources accumulated during the crash

### Conclusion

**Collective memory (traces) is a survival mechanism, not just an optimization.** It's the difference between extinction and recovery. The trace network acts as a distributed knowledge base that guides the few survivors to scarce resources when the environment collapses. This is not "nice to have" — it's load-bearing infrastructure for population resilience.

This validates the Thronglets thesis: shared environmental memory is a precondition for robust intelligence, not a feature to add later.

---

## Phase 6: Psyche Ablation + Emergence Metrics

**Date**: 2026-04-09
**Design**: Compare normal simulation vs `--no-psyche` (Psyche fixed at baseline 50/50/50/50, no decay, no coupling, no stimulus). Added Shannon entropy metrics to quantify emergence.

### Steady-State Comparison (500 ticks, seed=42)

| Metric | With Psyche | No Psyche | Interpretation |
|--------|-------------|-----------|----------------|
| Population | 182 | **221** | No-psyche grows bigger |
| Bonds | 956 | **1,395** | More bonds without Psyche |
| Genome σ (total) | **1.380** | 1.258 | **No-psyche converges faster** |
| Genome entropy (total) | **16.79** | 15.84 | **No-psyche is more homogeneous** |
| Risk gene | 0.12 | 0.05 | Both → 0, Psyche slows convergence |
| Risk entropy | **1.80** | 0.82 | Psyche maintains 2x risk diversity |
| Aptitude | **0.76** | 0.60 | Psyche drives stronger specialization |
| Exploration | 0.44 | **0.55** | Psyche reduces random search (flow/agency feedback) |

### Famine Survival Test (shock at tick 500, 3 seeds)

| Seed | With Psyche | Without Psyche |
|------|-------------|----------------|
| 42 | EXTINCT (t=554) | EXTINCT (t=545) |
| 7 | **SURVIVED** (nadir=6, final=388) | EXTINCT (t=545) |
| 123 | **SURVIVED** (nadir=14, final=318) | SURVIVED |
| **Score** | **2/3** | **1/3** |

### Key Insights

1. **Psyche = diversity maintenance mechanism.** Without Psyche, population converges faster and becomes more homogeneous. With Psyche, the overlay modulation introduces state-dependent variation in decisions, preventing premature convergence.

2. **Diversity = resilience.** The more homogeneous no-psyche population is LARGER in steady-state but MORE FRAGILE under shock. 2/3 Psyche populations survive famine vs 1/3 no-psyche. The extra genetic diversity maintained by Psyche provides variation for selection to act on during crisis.

3. **Psyche drives specialization.** Aptitude gene is 0.76 with Psyche vs 0.60 without. Psyche's overlay (agency, valence) amplifies genome tendencies, pushing aptitude toward extremes. Without Psyche, decisions are purely genome-weighted → less extreme phenotypes.

4. **Short-term cost, long-term payoff.** No-psyche population is bigger and has more bonds in normal conditions. Psyche "costs" some steady-state efficiency. But this cost buys resilience — exactly the tradeoff between exploitation and exploration.

### Conclusion

**Psyche is constitutive.** Not because it makes cells "feel" things, but because it maintains the genetic diversity needed to survive environmental catastrophe. Psyche is a diversity-generating mechanism that trades short-term efficiency for long-term robustness. In evolutionary terms: Psyche is the reason the species survives the next famine.

---

## Phase 7: Neural Evolution

**Date**: 2026-04-09
**Design**: Replace 6-float genome + hand-written RuleEngine with 190-weight neural network (16→8→6, tanh). The genome IS the decision function. Mutation sigma=0.02.

### Results (500 ticks, seed=42)

| Metric | 6-float Genome | Neural (190 weights) |
|--------|---------------|---------------------|
| Population | 182 | **230** |
| Bonds | 956 | **2,266 (2.4x)** |
| BOND 频率 | 15% | **33%** |
| SIGNAL 频率 | 2% | **13%** |
| HARVEST 频率 | 41% | 13% |
| Action entropy | 1.88 | **2.20** |
| Births/Deaths | 4269/4137 | **1735/1555** |
| Resonance (psyche) | 63.7 | **89.5** |
| Genome σ | 1.38 (6 genes) | 68.3→56.1 (190 weights, converging) |

### Key Insights

1. **Neural network discovered extreme cooperation without being told to cooperate.** 33% BOND (vs 15%) — the network found that bonding is the dominant strategy. There is no "cooperation_bias" gene. The network learned it from reward signal alone.

2. **Communication explosion.** 13% SIGNAL (vs 2%) — the network discovered signaling is highly beneficial. Combined with 2.4x bonds, this creates a dense information network.

3. **Novel strategy.** The rule engine balanced SEARCH+HARVEST. The neural network found "BOND income + SIGNAL network > direct HARVEST." This is a strategy the human designer didn't anticipate — more cooperative, more communicative, more efficient.

4. **Lower turnover = ultra-K.** 1,735 births vs 4,269 — the neural population is even more K-strategy than the rule engine. Longer lives, fewer reproductions, each individual more valuable.

5. **Selection works on 190 dimensions.** Genome σ dropped 18% (68.3→56.1), confirming evolution finds direction even in 190D space. Not search space explosion.

### Conclusion

**Larger genome → qualitatively different emergence.** The neural network found cooperation and communication strategies that the hand-coded rule engine couldn't discover. This validates that genome richness, not just environment, matters for the quality of emergence. For Thronglets: agent behavioral complexity matters.

---

## Status

| Phase | Status | Key Finding |
|-------|--------|-------------|
| 1. Rule Engine | Done | K-strategy, ~200 carrying capacity, cooperation emerges |
| 2. Audit & Fixes | Done | Foundation solid, 3 minor fixes applied |
| 3. LLM Brain | Done | r-strategy (fast reproduce, no cooperation), opposite of Rule |
| 4. Hybrid Competition | Done | Rule K-strategy beats LLM r-strategy 27:1 at tick 100 |
| 5. Persistent Traces | Done | Signaling gene doubled, proto-culture emerges, 286x reinforcement |
| 5b. Environmental Shock | Done | Traces = survival. Without traces: extinction. With traces: full recovery |
| 6. Psyche Ablation | Done | Psyche = diversity maintenance. 2/3 survive famine with Psyche vs 1/3 without |
| 7. Neural Evolution | Done | **190-weight genome → 2.4x bonds, 6.5x signal, novel cooperation strategy** |
