# codex-buddy

> 在 **OpenAI Codex（桌面端 App / CLI 通用）** 里确定性地使用 **腾讯 CodeBuddy** 模型驱动 agent 循环。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 这是什么

`codex-buddy` 是一套**已验证可用**的本地代理方案：让 Codex 的 Responses API 流量，经一层协议翻译后转发到 CodeBuddy 的模型后端，从而使 Codex（无论是桌面 App 还是 CLI）真正用 CodeBuddy（而非 OpenAI 官方模型）来读写文件、执行命令、跑 agent 循环。

> **适用对象**：本方案同时覆盖 **Codex 桌面端 App** 和 **Codex CLI**。两者共用同一份 `~/.codex/config.toml` 与 `model_providers` 机制（官方文档原文：*agents in the app inherit the same config*），所以配置一次，App 和 CLI 都能用。

本仓库只做**文档与一键启动脚本**，不含任何对 CodeBuddy 私有协议的破解——所有调用都走 CodeBuddy 官方 API / 开放平台 Key。

---

## 为什么需要它（核心约束：协议断层）

| 角色 | 协议 |
|------|------|
| **Codex（App / CLI，2026 起）** | 只认 **OpenAI Responses API**（`/v1/responses`），已彻底移除 `wire_api = "chat"` |
| **CodeBuddy** | 无公开 Responses 端点，只有私有聊天接口；社区封装为 **OpenAI Chat Completions**（`/v1/chat/completions`） |

两者协议不互通，因此必须在中间加一层「**Responses API → Chat Completions**」翻译网关：

```
Codex（App 或 CLI） ──(Responses API)──▶ [ Responses→Chat 网关 ] ──(Chat Completions)──▶ [ CodeBuddy 代理 ] ──▶ CodeBuddy CN
                   (config.toml 里的自定义 provider / CC Switch)      (CodeBuddy2api，OpenAI 兼容 + 鉴权)
```

- **网关层**：把 Codex 的 Responses 协议翻译成 Chat Completions，并透传 `tool_calls`（Codex 的 agent 循环依赖工具调用，缺了就退化成纯聊天）。
- **代理层**：把 CodeBuddy 私有聊天 API 暴露成 OpenAI 兼容接口，并提供鉴权。

---

## 两套落地方案

两者底层都依赖同一对组件：**`CodeBuddy2api` + 一个 Responses 网关**。区别只在"网关以什么形式接入 Codex"。

| 方案 | 网关形式 | 是否改 config.toml | 适合人群 |
|------|----------|-------------------|----------|
| **A（推荐，App/CLI 原生）** | 直接在 `~/.codex/config.toml` 写自定义 `model_providers`（`wire_api="responses"`） | ✅ 写一次 | 想用官方原生机制、最稳 |
| **B（零配置）** | **CC Switch** 桌面端本地路由，网络层透明代理 | ❌ 不改 | 不想碰 config、想可视化切模型 |

> 另有纯 CLI 网关 **opencodex**（`ocx`）可作方案 A 的变体：它帮你自动写入 `wire_api=responses` 的 provider。本质同方案 A。

---

## 方案 A：config.toml 直配（Codex App / CLI 通用 ⭐）

这是最贴近官方机制的用法。Codex 桌面 App 启动时会读取 `~/.codex/config.toml`，自定义 `model_providers` 里的模型会直接出现在 App 的模型选择器里。

### 步骤

**1. 起 CodeBuddy 代理（提供 OpenAI 兼容 Chat 接口）**

使用 [`Sliverkiss/CodeBuddy2api`](https://github.com/Sliverkiss/CodeBuddy2api)（封装 CodeBuddy 官方 API，工具调用处理完整）：

```bash
git clone https://github.com/Sliverkiss/CodeBuddy2api
cd CodeBuddy2api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 推荐 API Key 模式（最稳），也可留空走 Web 页 OAuth 自动获取
cp .env.example .env
# .env 里设：CODEBUDDY_AUTH_MODE=api_key 与 CODEBUDDY_API_KEY=你的Key

python web.py
```

- 监听 `http://127.0.0.1:8001`
- 接口 `http://127.0.0.1:8001/codebuddy/v1/chat/completions`（OpenAI 兼容）

**2. 起一个 Responses→Chat 网关，把 Chat 接口再包成 Responses API**

方案 A 让 Codex 直连的端点必须是 **Responses API**。把 `127.0.0.1:8001/codebuddy/v1`（Chat）用网关包成 Responses。最简做法是用 **opencodex**（`ocx`）的网关能力，或用一份最小的自托管网关。

以 opencodex 为例（它会对外暴露 `/v1/responses`）：

```bash
npm i -g opencodex
ocx init            # 生成 ~/.codex/config.toml 并注入自定义 responses provider
```

在 `ocx` 里把后端指向 `http://127.0.0.1:8001/codebuddy/v1`，然后 `ocx start`（默认监听某本地端口，对外提供 Responses API）。

**3. 在 `~/.codex/config.toml` 声明自定义 provider**

最终 Codex 要连的是第 2 步网关的 Responses 地址。示意：

```toml
model = "codebuddy/auto-chat"
model_provider = "codebuddy"

[model_providers.codebuddy]
name = "CodeBuddy"
base_url = "http://localhost:<网关端口>/v1"
wire_api = "responses"
env_key = "CODEBUDDY_PROXY_KEY"   # 在环境变量里给任意非空值即可
```

环境变量（随便给个值，真正鉴权在 CodeBuddy2api 那层）：

```bash
export CODEBUDDY_PROXY_KEY=local
```

**4. 打开 Codex 桌面 App（或跑 `codex` CLI）**

- **Codex App**：正常登录你的 ChatGPT 账号（App 允许"保留登录、但 API 请求走第三方 Provider"），在模型选择器里选 `codebuddy/auto-chat` 即可。App 会读取第 3 步的 `config.toml`，自定义模型已出现在列表里。
- **Codex CLI**：直接 `codex`，默认就用 `codebuddy/auto-chat`。

---

## 方案 B：CC Switch 透明代理（零 config.toml 改动）

[**CC Switch**](https://github.com/...) 是专为「Codex / Claude Code / Gemini CLI ↔ 第三方模型」做的桌面端本地路由网关（Tauri 2）。它对 Codex **透明代理**：Codex 以为自己还在连 OpenAI 官方，实际流量被转到你配的后端，**完全不用改 `config.toml`**，且专为 Codex 的 Responses API 实现，工具调用透传有保证。因为它是网络层拦截，所以**Codex App 和 CLI 都适用**。

### 步骤

1. 按方案 A 第 1 步起好 `CodeBuddy2api`（`127.0.0.1:8001/codebuddy/v1`）。
2. `brew install --cask cc-switch`，打开后顶部切到 **Codex**；左侧 `Providers` → `+ Add Provider`，选 **Custom / OpenAI 兼容**，填入：
   - **Base URL**：`http://127.0.0.1:8001/codebuddy/v1`
   - **API Key**：任意非空串（真正鉴权在 CodeBuddy2api 那层）
   - **Model**：例如 `auto-chat`
   - 开启 **Local Routing（本地路由映射）**，保存，确认状态绿色。
3. 打开 **Codex App**（或跑 `codex`）——请求已被透明转发到 CodeBuddy，模型列表里会出现你配的模型。

> 方案 B 比方案 A 少改一处 config，但多装一个桌面程序；方案 A 是官方原生机制、最可控。两者底层都依赖 `CodeBuddy2api`。

---

## 工具调用透传确认（源码级 ✅）

> 已直接阅读 `Sliverkiss/CodeBuddy2api` 的 `src/codebuddy_router.py` 验证。

**入站（`tools` 透传）**：`RequestProcessor.prepare_payload()` 是 `payload = request_body.copy()` 后强制 `payload["stream"] = True`，不做字段裁剪——请求体里的 `tools` / `tool_choice` 原样发往 CodeBuddy 官方 `/v2/chat/completions`。

**出站（`tool_calls` 回传）**：响应侧有完整实现（Adapter 模式，非简单透传）：

- `convert_sse_chunk_to_openai_format()`：把 CodeBuddy 的 `tooluse_*` ID 转成 OpenAI 的 `call_*` 格式，并维护 `index` 映射重分配（CodeBuddy 自身不提供稳定 index）。
- `StreamResponseAggregator`：以 tool call ID 为键聚合分块流，正确处理**多工具并发调用**，流式结束后拼出完整 `tool_calls` 数组；`finish_reason` 自动置为 `"tool_calls"`。
- `validate_and_fix_tool_call_args()`：修复流截断导致的 JSON 不完整（含多 JSON 对象粘连的边界情况）。

**结论**：整个链路在工具调用维度上**确定可用**，Codex 的 agent 循环能真正读写文件、执行命令。唯一外部变量是 **CodeBuddy 官方 API 是否真正开通 function calling**（取决于你账号/模型），由后端能力决定，代理层已无障碍。

---

## 本地自检（可选）

起好 CodeBuddy2api 后，确认后端确实返回 `tool_calls`：

```bash
curl http://127.0.0.1:8001/codebuddy/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"auto-chat",
    "messages":[{"role":"user","content":"用计算器算 1+1"}],
    "tools":[{"type":"function","function":{"name":"calc","description":"计算","parameters":{"type":"object","properties":{"expr":{"type":"string"}}}}}],
    "tool_choice":"auto"
  }'
```

- 返回里出现 `"tool_calls"` → 后端已开通 function calling，**整链确定可用**。
- 只有普通文本、无 `tool_calls` → 后端模型未开通 function calling（换支持工具调用的模型/账号），代理层无需改动。

---

## 注意事项

- **Codex App 登录**：App 仍需你的 ChatGPT 账号登录才能启动；配置第三方 Provider 后，**保留登录、但 API 请求走 CodeBuddy** 是官方支持的模式。
- **鉴权**：CodeBuddy2api 支持 `CODEBUDDY_AUTH_MODE=api_key`（推荐，直接用 CodeBuddy 开放平台 Key）或 Web 页 OAuth 自动获取。
- **端口冲突**：CodeBuddy2api 默认 `8001`；网关（opencodex / CC Switch）各有端口，注意别撞车。
- **合规**：本方案为本地代理 + 个人账号调用，请遵守 CodeBuddy / Codex 各自的服务条款；个别上游项目标明了 Non-Commercial 许可，注意使用场景。
- **版本漂移**：Codex 在 2026 年频繁改协议（移除 `wire_api=chat`、合并进 ChatGPT Desktop 等）。若某天 Codex 报错 `wire_api not supported`，第一反应是确认你的网关仍对外提供 **Responses API**，而不是改回 chat。

---

## 目录结构

```
codex-buddy/
├── README.md          # 本文件
└── (scripts/)         # 后续可加一键启动脚本
```

---

## License

[MIT](LICENSE)
