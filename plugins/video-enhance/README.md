# Video Enhance

一个面向 Codex 的视频创建、检查与分析 Plugin。视频创建通过隔离的
Computer Use 子代理操作 provider UI；检查与分析通过本机 stdio MCP
服务提供统一接口。分析核心层不依赖具体模型；当前只实现 MiniMax
provider（MiniMax-M3），后续 provider 可通过 registry 增量加入。

## 创建视频

通过 `$video-enhance:create <provider>` 调用创建技能。v1 支持
`google-flow`：

```text
$video-enhance:create google-flow model=omni-flash duration=10s aspect_ratio=16:9 count=2 max_credits=90
```

每个最终视频都会被拆成一个独立的 Flow `x1` 任务，由一个全新的叶子
子代理负责。多个视频串行执行，避免同时操作 Safari。主代理维护整次调用
的总积分预算；子代理会在最终生成按钮前读取页面实时费用，超出分配预算时
先通知主代理并暂停。预算批准、用户接管和同一视频的一次重试都复用原子
代理，不会把第二个视频交给它。

若需要把新生成的多个片段拼成一条成片，可使用
`stitch=true segments=<n>` 或直接用自然语言说明。例如“两段拼成一条”
会解析为 `count=1 segments=2`，仍然只使用一个专属叶子代理。代理按顺序
以 `x1` 生成并验证每段视频，再在本地硬切拼接；兼容流优先无重编码复制，
不兼容时才执行高质量 H.264/AAC 规范化。拼接本身不消耗 Flow 积分，
当前不包含转场、裁剪或任意已有视频编辑。连续叙事默认把上一段最终解码帧
作为下一段 `start_frame`，同时延续人物、构图、镜头方向和运动状态；
因此不会像简单重复视频那样在拼接点重置场景。

默认复用名为 `Video Enhance` 的 Flow 项目。支持文生视频、明确标注的
素材参考图和首尾帧；不支持编辑已有视频。运行时要求安装
`$computer-use:computer-use`，并使用 Safari 中已有的 Google 登录。
技能不保存凭据、不购买积分、不升级套餐、不删除已有 Flow 内容。生成的
MP4 默认保存到当前工作区的 `outputs/video-enhance/<run-id>/`，并通过
`video_inspect` 验证。

## 分析视频

通过 `$video-enhance:analyze` 调用分析技能。MCP 服务标识为
`video-enhance`，但公开工具名保持稳定：

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
