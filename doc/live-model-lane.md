# Live Model Lane

`primordial-soup` 现在有两条明确分开的执行路径：

- `Admission / Replay Factory`
  - 规则化
  - 可重复
  - 不接外部模型
- `Live Model Lane`
  - 接外部模型
  - 用于真实 live soup 实验
  - 用于跨 provider / model 的稳定对比

这份文档只描述第二条。

## 边界

外部模型只服务 live soup simulation，不进入 admission / replay 主线。

不接入外部模型的模块：

- [admission_factory.py](/Users/wutongcheng/Desktop/primordial-soup/admission_factory.py)
- [emergence_harness.py](/Users/wutongcheng/Desktop/primordial-soup/emergence_harness.py)
- [tools/build_calibration_profile.py](/Users/wutongcheng/Desktop/primordial-soup/tools/build_calibration_profile.py)
- [tools/build_replay_bundle.py](/Users/wutongcheng/Desktop/primordial-soup/tools/build_replay_bundle.py)

接外部模型的模块：

- [model_lane.py](/Users/wutongcheng/Desktop/primordial-soup/model_lane.py)
- [run.py](/Users/wutongcheng/Desktop/primordial-soup/run.py)
- [tools/run_model_benchmark.py](/Users/wutongcheng/Desktop/primordial-soup/tools/run_model_benchmark.py)

## Profile Registry

profile registry 固定在 [config/model_profiles.json](/Users/wutongcheng/Desktop/primordial-soup/config/model_profiles.json)。

当前 schema：

```json
{
  "schema_version": 1,
  "default_profile_id": "kimi",
  "profiles": [
    {
      "profile_id": "kimi",
      "provider": "kimi",
      "transport": "anthropic_messages",
      "api_url": "...",
      "model": "kimi-k2.5",
      "api_key_env": "KIMI_API_KEY",
      "max_tokens": 40,
      "max_workers": 40
    }
  ]
}
```

约束：

- `profile_id` 必须唯一
- `transport` 目前只允许：
  - `anthropic_messages`
  - `openai_chat_completions`
- `provider` 只是 benchmark metadata，不是系统角色
- profile 可以指定 `api_key_env`
- CLI 显式参数会覆盖 profile

## Env 约定

当前内置 profile：

- `kimi`
  - 只认 `KIMI_API_KEY`
- `anthropic-compatible`
  - `ANTHROPIC_API_KEY`
- `openai-compatible`
  - `OPENAI_API_KEY`

如果 profile 已声明 `api_key_env`，系统只会读取这个变量。
如果 profile 没有显式 `api_key_env`，才会退回 transport 的默认 env。

在 macOS GUI 环境下，live lane 会同时检查：

- 当前进程环境
- `launchctl getenv <NAME>`

所以 Codex desktop / GUI app 的可见性，以 `launchctl` 为准。

## 运行方式

单次 live run：

```bash
python3 run.py --llm --model-profile kimi
python3 run.py --hybrid --model-profile kimi
python3 run.py --llm --model-profile openai-compatible
```

高级 override：

```bash
python3 run.py \
  --llm \
  --model-profile kimi \
  --transport openai_chat_completions \
  --api-url https://api.openai.com/v1/chat/completions \
  --model gpt-4.1-mini \
  --api-key "$OPENAI_API_KEY"
```

说明：

- `--model-profile` 先加载 profile
- 显式 CLI 参数再覆盖 profile
- `--harness` 会完全绕开 provider/profile 初始化

只读诊断：

```bash
python3 run.py --list-model-profiles
python3 run.py --check-model-profile kimi
```

`--check-model-profile kimi` 会输出：

- profile 是否存在
- provider / transport / api_url / model
- 需要哪个 env
- 当前进程是否可见
- `launchctl` 是否可见
- 是否 locally ready

不会打印 secret 值本身。

注意：

- `ready=true` 只表示当前机器上的 profile 配置和 secret 可见性已经满足本地 preflight。
- 它不代表远端 provider 已经鉴权成功。
- 真正的连通性仍应再跑一次最小 smoke run：

```bash
python3 run.py --llm --model-profile kimi --ticks 1 --pop 2 --print-every 10
```

## Benchmark Lane

benchmark runner：

```bash
python3 tools/run_model_benchmark.py --model-profile kimi
```

常用调试跑法：

```bash
python3 tools/run_model_benchmark.py \
  --model-profile kimi \
  --modes llm,hybrid \
  --seeds 42,7,123 \
  --ticks 20 \
  --pop 8 \
  --print-every 20
```

输出目录：

```text
data/benchmarks/<profile-id>/<timestamp>/
  llm_seed42.json
  hybrid_seed42.json
  summary.json
```

`summary.json` 至少包含：

- `profile_id`
- `timestamp`
- `benchmark_dir`
- `runs`

每个 `run` 至少包含：

- `mode`
- `seed`
- `profile`
- `final_population`
- `total_births`
- `total_deaths`
- `action_distribution`
- `brain_counts`
- `llm_stats`

## 架构收口

这条 lane 当前的责任边界：

- [model_lane.py](/Users/wutongcheng/Desktop/primordial-soup/model_lane.py)
  - profile registry
  - transport adapter
  - key resolution
- [run.py](/Users/wutongcheng/Desktop/primordial-soup/run.py)
  - CLI
  - live simulation wiring
  - summary extraction
- [soup.py](/Users/wutongcheng/Desktop/primordial-soup/soup.py)
  - prompt / parse / fallback
  - simulation runtime
- [tools/run_model_benchmark.py](/Users/wutongcheng/Desktop/primordial-soup/tools/run_model_benchmark.py)
  - repeated live runs
  - benchmark artifact generation

## 加新模型的步骤

以后接入新 provider / model，默认流程：

1. 在 [config/model_profiles.json](/Users/wutongcheng/Desktop/primordial-soup/config/model_profiles.json) 增加一个新 profile
2. 若现有 transport 不够，再在 [model_lane.py](/Users/wutongcheng/Desktop/primordial-soup/model_lane.py) 增加新的 `TransportAdapter`
3. 先用小规模 live run 验证：
   - `--ticks 1`
   - `--pop 2`
4. 再跑 benchmark lane 做稳定对比

只有当 provider 的 HTTP 形状和现有 transport 都不兼容时，才需要改 Python 代码。

## Kimi Readiness

这台机器上，`~/.zshrc` 不再被视为 Codex desktop 的 secret 真相源。

标准检查顺序：

1. `python3 run.py --check-model-profile kimi`
2. `launchctl getenv KIMI_API_KEY`
3. `python3 run.py --llm --model-profile kimi --ticks 1 --pop 2 --print-every 10`

如果第 2 步为空，说明 GUI / Codex 会话不会稳定拿到 Kimi key；应先修 `launchctl` 用户环境，再跑 live soup。
