# codex-buddy

通过本地 Responses API 网关，让 Codex 使用 CodeBuddy 兼容的模型。

调度模式下：GPT 负责规划和总结，CodeBuddy 下的模型负责执行任务，结果仍返回当前 Codex 对话。

```text
Codex 对话
  → codex-buddy-gateway
  → GPT 规划
  → CodeBuddy 模型执行
  → GPT 总结
  → 返回 Codex
```

## 项目内容

- `codex-buddy-gateway.py`：将 `/v1/responses` 转换为 Chat Completions。
- `gpt-kimi-orchestrator.py`：GPT 调度器和 CodeBuddy Worker。
- `test_gateway_dryrun.py`：使用 mock 上游的离线测试。
- `scripts/setup-codebuddy2api.sh`：准备外部 CodeBuddy2api 依赖。

网关代码不会修改 Codex 登录文件。若需要保留官方登录状态，不要使用会改写 Codex 配置的工具。

## 准备依赖

网关默认连接：

```text
http://127.0.0.1:8001/codebuddy/v1
```

准备外部 CodeBuddy2api：

```bash
./scripts/setup-codebuddy2api.sh
```

按提示配置 CodeBuddy API Key 和版本环境。密钥不存放在本仓库中。

安装网关依赖：

```bash
pip install -r requirements.txt
```

## 直接网关模式

确认上游准备好后，再启动网关：

```bash
python codex-buddy-gateway.py
```

监听地址：

```text
http://127.0.0.1:8787/v1
```

在单独的 Codex API 配置/Profile 中使用该地址，并选择 Responses 模式。请求中的模型名会转发给 CodeBuddy2api。

可配置参数：

```bash
export CODEBUDDY_BASE_URL="http://127.0.0.1:8001/codebuddy/v1"
export CODEBUDDY_API_KEY="dummy"
export CODEBUDDY_MODEL="kimi-k3"
export GATEWAY_HOST="127.0.0.1"
export GATEWAY_PORT="8787"
```

## GPT 调度模式

启动网关前设置：

```bash
export CODEBUDDY_ORCHESTRATE=1
export ORCHESTRATOR_API_KEY="你的 OpenAI API Key"
export ORCHESTRATOR_MODEL="gpt-4o-mini"
export WORKER_BASE_URLS="http://127.0.0.1:8001/codebuddy/v1"
export WORKER_DEFAULT_MODEL="kimi-k3"
export WORKER_FALLBACK_MODEL="hy3-high"
```

每次请求中，GPT 读取当前对话并拆分任务，CodeBuddy 模型执行子任务，GPT 最后汇总并返回一个回答。未设置 `CODEBUDDY_ORCHESTRATE=1` 时，网关只做协议转换。

## 不启动服务进行验证

```bash
python3 test_gateway_dryrun.py
```

真实使用时，需要分别运行上游服务和本地网关。本 README 不表示任何服务已经启动。

## License

[MIT](LICENSE)
