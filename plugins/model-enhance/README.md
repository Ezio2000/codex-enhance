# Model Enhance

Codex Enhance 商城中的自包含插件，通过本地 STDIO MCP 把明确、有限的文本任务委派给
OpenAI-compatible 或 Anthropic-compatible 模型。配套技能调用名为
`$model-enhance:consult`。

```text
Codex / ChatGPT Desktop ──stdio──> Model Enhance ──HTTPS──> compatible API
```

MCP 进程不监听端口。它只在调用外部模型 API 时发出 HTTP(S) 请求。

## 产品边界

插件通过 `.mcp.json` 在 ChatGPT 桌面端的 Work/Codex 或 Codex CLI 中启动 STDIO MCP。
它不需要远程 MCP 地址，也不包含 `.app.json`。

如果以后要让 ChatGPT Web 直接使用或提交到公共插件目录，需要另行部署可联网访问的
MCP 服务，在 ChatGPT Developer mode 创建 App，再把 App ID 写入 `.app.json` 和插件
manifest 的 `apps` 字段。这是独立的发布阶段，不改变当前“本地 STDIO、逐次传 Key”的
实现。

## 凭据边界

插件不从本地配置、环境变量或系统钥匙串加载供应商凭据，也不缓存 API Key。调用模型
必须在每次 MCP 工具调用中显式提供：

- `protocol`：`openai` 或 `anthropic`
- `base_url`：本次请求的兼容 API 根地址
- `api_key`：只用于本次请求
- `model`：`ask_model` 使用的准确模型 ID
- `anthropic_auth_mode`：Anthropic 协议可选 `x-api-key`（默认）或 `bearer`

`api_key` 在工具 JSON Schema 中标记为 `writeOnly`，上游成功和错误响应也会经过精确
脱敏。但 MCP Host 仍可能把工具参数写入任务历史、调试日志或遥测；只有在接受这个边界
时才把 Key 提供给调用模型。

模型同时控制 `base_url` 和 Key。通用桥接器无法把任意公网域名与凭据做密码学绑定，
也不是网络沙箱。两个工具都标记为非只读，必须逐次审批并核对目标地址；敏感内网环境还
应使用进程级网络策略或出口白名单。

## 工具

### `ask_model`

调用指定兼容模型，返回最终文本、用量、finish reason 和上游 request ID。插件不返回
thinking/reasoning，也不执行上游模型请求的工具调用。

```json
{
  "protocol": "openai",
  "base_url": "https://api.example.com/v1",
  "api_key": "<本次调用显式传入>",
  "model": "provider-model-id",
  "prompt": "Review this implementation and list concrete defects."
}
```

### `list_models`

使用本次调用提供的 `base_url` 和 `api_key` 查询上游模型列表。是否支持该接口取决于兼容
服务商。

## 安装

先添加 Codex Enhance 商城，再安装插件：

```text
codex plugin marketplace add Ezio2000/codex-enhance --ref main
codex plugin add model-enhance@codex-enhance
codex plugin list
```

安装或更新后请新建任务，让 Codex/ChatGPT Desktop 加载新的 Skill 和 MCP 工具。

## 开发验证

项目只使用 `uv`：

```bash
uv sync --locked --all-groups
uv run --locked pytest
uv run --locked python scripts/stdio_smoke.py --list-tools
```

普通测试不需要真实 Key。可选 live 测试只从测试进程的通用变量读取路由，然后仍把 Key
作为 MCP 工具参数传入：

```bash
export MODEL_ENHANCE_LIVE_API_KEY="..."
export MODEL_ENHANCE_LIVE_MODEL="provider-model-id"
export MODEL_ENHANCE_LIVE_OPENAI_BASE_URL="https://api.example.com/v1"
export MODEL_ENHANCE_LIVE_ANTHROPIC_BASE_URL="https://api.example.com/anthropic"
export MODEL_ENHANCE_LIVE_ANTHROPIC_AUTH_MODE="x-api-key"
MODEL_ENHANCE_RUN_LIVE_TESTS=1 uv run --locked pytest -m live
```

也可用 `MODEL_ENHANCE_LIVE_OPENAI_API_KEY`、`MODEL_ENHANCE_LIVE_ANTHROPIC_API_KEY` 和对应
协议的 `..._MODEL` 覆盖共享测试值。不要使用 `set -x`，不要提交测试凭据或供应商原始
响应。
