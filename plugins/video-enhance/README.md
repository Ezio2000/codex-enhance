# Video Enhance

一个面向 Codex 的视频检查与分析 Plugin，底层通过本机 stdio MCP 服务提供统一接口。核心层不依赖具体模型；当前只实现 MiniMax provider（MiniMax-M3），后续 provider 可通过 registry 增量加入。

通过 `$video-enhance:analyze` 调用技能。MCP 服务标识为 `video-enhance`，但公开工具名保持稳定：

## 工具

- `video_config_status`：安全检查配置状态和远端删除策略，不返回密钥。
- `video_inspect`：本地探测，不上传、不消耗模型额度。
- `video_analyze`：规范化、上传、分析、校验结果与时间戳，并按配置清理或保留远端文件。

公开 profile 为 `balanced`、`temporal`、`ocr`；provider 可用 `auto` 或配置实例名。输出始终使用统一的 `VideoAnalyzeResult`，其中包含 route、usage、coverage、warnings 和 `completed|partial` 状态。

## 配置 API Key

运行时默认读取 `~/.config/video-enhance/config.toml`。也可用 `VIDEO_ENHANCE_CONFIG` 指定另一个配置文件路径；API Key 不接受环境变量或 MCP 参数传入。

```bash
mkdir -p ~/.config/video-enhance
cp config.example.toml ~/.config/video-enhance/config.toml
chmod 700 ~/.config/video-enhance
chmod 600 ~/.config/video-enhance/config.toml
```

然后编辑 `providers.minimax.api_key`。密钥不会进入 Plugin、Codex MCP 清单、工具参数或日志。配置格式见 [config.example.toml](./config.example.toml)。

## Provider 抽象

`core/contracts.py` 定义 `VideoProvider`、能力声明、统一请求和响应；`core/pipeline.py` 只依赖这些协议。MiniMax 的 Files API、`mm_file://`、M3 tool call、profile 参数映射和远端删除全部位于 `providers/minimax/`。新增 provider 时实现同一协议并在 `providers/registry.py` 注册即可，无需新增 MCP 工具。

媒体会转换成无音频的 H.264/yuv420p/CFR 30fps MP4，并追加不遮挡原画面的时间码栏。默认的 `delete_remote_files = true` 会在分析后请求删除远端文件；设为 `false` 会保留上传内容，并在配置状态和分析结果中明确暴露该策略。删除失败也会作为告警返回，即使分析本身同时失败也不会静默隐藏远端残留风险。即使供应商返回成功，核心仍会校验 JSON Schema、时间戳范围、顺序与全片覆盖。

## 开发验证

```bash
uv sync --locked --all-groups
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python scripts/stdio_smoke.py --list-tools
```
