# Primordial Soup — Evolution Simulation Plan

> 独立项目，不影响其他 Oasyce 组件。从 Psyche 主体性困境推导出的实验。

---

## 为什么做这个

1. Psyche 在 LLM 上做不到 constitutive self（只能被查询，不能调制行为）
2. 但如果 Psyche 是决策函数的**直接输入**，它就是真正的 self-state
3. Sigil 三公理 + 六事件 = 完整的进化引擎
4. 不需要大算力——进化的算力来自死亡和选择压力

---

## 项目结构：独立 Repo

```
~/Desktop/primordial-soup/
    soup.py           # 全部模拟代码 (~600 行)
    run.py            # 入口 + 配置
    README.md         # 实验记录
    requirements.txt  # Phase 1 无外部依赖
```

**独立 repo，不依赖 oasyce-sdk、Psyche、Thronglets 任何代码。** Phase 1 完全自包含。Phase 2/3 再按需引入。

---

## 三阶段

### Phase 1：规则引擎（成本 $0）

纯 Python，零依赖，笔记本跑。验证进化动力学能不能工作。

### Phase 2：接入真实 Psyche + Thronglets

HTTP 调用，不 import 代码，通过 API 松耦合。

### Phase 3：LLM 决策

用 Qwen-turbo API 替换规则引擎。100K 决策 ≈ ¥100。

---

## Phase 1 详细设计

### 数据结构

**Genome（遗传单元，5 个 float）：**

| 基因 | 范围 | 含义 |
|------|------|------|
| fork_threshold | [0.3, 0.9] | 能量达到多少比例时尝试繁殖 |
| exploration_rate | [0, 1] | 随机搜索 vs 定向搜索 |
| cooperation_bias | [0, 1] | BOND 倾向 |
| signal_frequency | [0, 1] | 留痕频率 |
| risk_tolerance | [0, 1] | 搜索距离 / 决策温度 |

变异：FORK 时每个权重加 `gauss(0, 0.05)`，clip 到有效范围。

**PsycheState（简化 4D，移植自 Psyche v11）：**

```
order     = 50  # 序——内在一致性
flow      = 50  # 流——与环境的交换
boundary  = 50  # 界——自我/非我的区分
resonance = 50  # 振——与他者的共振
```

衰减率（来自 chemistry.ts）：order=0.9952, flow=0.9967, boundary=0.9991, resonance=0.9979 per tick。

耦合（来自 applyMutualInfluence）：
- order 低 → boundary 下降
- flow 高 → order 上升
- resonance 高 → boundary 稳定
- 耦合率 0.03

**Overlay（从 4D 投影，来自 overlay.ts）：**
- arousal, valence, agency, vulnerability
- 调制决策：agency 低 → 不太可能 FORK；valence 负 → 更可能 REST

**Cell（一个 Sigil Loop）：**

```
sigil_id:   str
energy:     float (初始 100，0 时死亡)
psyche:     PsycheState
genome:     Genome
age:        int
position:   (x, y) 在网格上
lineage:    [parent_ids...]
bonds:      {bonded_cell_ids}
alive:      bool
```

### Tick 循环（每个 cell）

```
1. energy -= 1                          # 代谢
2. if energy <= 0: DISSOLVE             # 死亡
3. psyche 衰减 → 向 baseline 回归       # 状态衰减
4. psyche 维度间耦合                     # 互相影响
5. bond 收入：每个范围内的 bond +1（上限 3）
6. 感知：附近的资源、信号、cell（半径 3）
7. 计算 overlay（从 psyche 状态投影）
8. 决策引擎选择动作（genome × psyche × 感知）
9. 执行动作，支付成本，获得回报
10. 动作结果影响 psyche 状态
11. age += 1
```

### 动作表

| 动作 | 能量成本 | 效果 | Psyche 影响 |
|------|---------|------|------------|
| SEARCH | 2 | 找到资源 → 获得能量 | 成功: order+3 flow+5; 失败: order-2 flow+2 |
| FORK | 55% energy | 子代 = 变异基因 + 45% 能量; 10% 熵损 | order-5 flow+8 boundary+3 |
| BOND | 1 | 互相绑定，共享信号，+1/tick 被动收入 | resonance+10 boundary-3 flow+5 |
| SIGNAL | 1 | 留痕（"food_here" / "seeking_bond"） | flow+2 resonance+3 |
| REST | 0 | 无消耗，psyche 恢复 | order+4 flow-2 |

### 决策引擎（规则版）

每个动作计算得分 → softmax 采样（温度 = 0.1 + risk_tolerance × 0.9）：

- SEARCH 得分 ∝ 饥饿度 × exploration_rate × agency
- FORK 得分：能量不够 → 0；否则 ∝ 成熟度 × agency
- BOND 得分：没邻居 → 0；否则 ∝ cooperation_bias × valence
- SIGNAL 得分 ∝ signal_frequency × (有信息可分享)
- REST 得分 ∝ 疲劳度 × vulnerability

**接口是 pluggable 的**——Phase 3 直接替换为 LLM。

### 环境

- 30×30 环面网格（边缘相连）
- 资源：每 tick 每格 2% 概率生成 uniform(5, 15) 能量
- 信号：每 tick 衰减 ×0.9，<0.1 时消失（~20 tick 寿命）
- 感知半径：3 格

### 资源预算

```
资源流入/tick = 900格 × 0.02 × 10平均 = 180 能量
50 cells × 1 代谢 = 50 能量/tick
剩余 130 → 支持增长到 ~130-180 cells（自然承载力）
```

### 观察指标

| 指标 | 含义 |
|------|------|
| 种群数量 | 承载力是否涌现 |
| 平均寿命 | 生存策略是否进化 |
| BOND 数量 | 合作是否自发出现 |
| 基因均值/方差 | 选择压力是否在工作 |
| 动作分布 | 有没有分工涌现 |
| 世系深度 | 有没有成功的"王朝" |
| Psyche 分布 | 集体心理状态是什么样 |

每 50 tick 打印一次摘要。

### 默认配置

```python
width = 30
height = 30
resource_rate = 0.02
initial_population = 50
mutation_sigma = 0.05
perception_radius = 3
ticks = 1000
seed = 42
```

---

## Phase 2：接入真实子系统（松耦合）

**Psyche**：每个 cell 通过 HTTP (port 3210) 调用 PsycheEngine，用 sigilId 隔离。
**Thronglets**：通过 HTTP (port 6668) 调用，grid position 映射到 context string，signal 变成真实的 signal_post()。
**Chain**：可选。GENESIS/FORK/BOND/DISSOLVE 调链上 Sigil 模块，记录进化历史。

适配器接口：
```python
class SubstrateAdapter(Protocol):
    def perceive(self, cell_id, context) -> tuple[PsycheState, list[Signal]]: ...
    def act(self, cell_id, action, outcome, context) -> PsycheState: ...
```

Phase 1 用 `InMemorySubstrate`，Phase 2 换 `LiveSubstrate`。

---

## Phase 3：LLM 决策

用 Qwen-turbo API 替换 RuleEngine。

```
System: You are a cell. Survive and reproduce.
State: energy={e}, order={o}, flow={f}, boundary={b}, resonance={r}
Nearby: {resources}, {signals}, {neighbors}
Choose: SEARCH/FORK/BOND/SIGNAL/REST
Reply JSON: {"action":"...","target":"..."}
```

- 每次决策 ~220 tokens → ¥0.001
- 100 cells × 1000 ticks = 100K 决策 ≈ ¥100 (~$14)

需要 `openai` Python 包（DashScope 兼容 OpenAI 协议）。

---

## Psyche 在这里的意义

**Phase 1 中 Psyche 第一次真正有意义。**

Cell 的 Psyche 状态不是标签、不是 prompt injection——它是决策函数的**直接输入参数**。order 低的 cell 真的会做出混乱的选择，不是因为有人告诉它"你很混乱"，而是因为 order 影响了 softmax 的得分。

这不是表演，是**构成性的**（constitutive）。

---

## 风险与未知

| 风险 | 缓解 |
|------|------|
| 种群爆炸 | FORK 消耗 55% 能量 + 10% 熵损，资源有限 |
| 过早收敛 | sigma=0.05 保证变异幅度 |
| 灭绝 | 资源预算 180 >> 代谢 50 |
| 食物设计隐式决定结果 | 纯随机生成，不偏向任何位置 |
| 10 万代无涌现 | 记录实验，调参，诚实面对 |
