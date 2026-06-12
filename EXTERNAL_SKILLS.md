# External Skills 约定

`External_Skills/` 目录由**人工**增减维护；**AI / Agent 不得修改**其中任何文件。

## 消化流程

当用户要求「消化 external skills」时：

1. **只读**遍历 `External_Skills/`（含 `Transcribe_Skills/`）
2. 将能力**合并进项目根目录**（`scripts/`、`.cursor/skills/`、`requirements-*.txt`、文档）
3. **不**回写、不删除 External_Skills 源文件

## 已消化对照

| External | 项目内实现 | 差异与取舍 |
|----------|------------|------------|
| `bilibili-transcribe` | `scripts/bilibili_fetch.py` + `rw_video.py` | **项目优先 B 站 API 字幕**（快、准）；External 用 yt-dlp + SenseVoice，适合无字幕视频。不重复安装 yt-dlp 流水线。 |
| `douyin-transcribe` | `scripts/douyin/` + `douyin_fetch.py` | 下载逻辑取自 External（iesdouyin + 移动端 UA），改为 **requests**（Windows 友好）；批量列表 + `douyin_sync.json`；ASR：Py≤3.12 **SenseVoice**，3.13+ **faster-whisper-small**；2025-12~2026-06 钱加贝 **243 篇**已回填并 ing。 |
| `tiktok-transcribe` | `scripts/tiktok_fetch.py` → `douyin_fetch.py` | 本项目中 **fetch tiktok = 抖音（钱加贝）**；国际 TikTok 仍保留 External 参考，未接入 daily。 |
| `bilibili-transcript`（Cursor skill） | 单链面临时转录 | 与 `bilibili-transcribe` 同类；日常增量以 `bilibili_fetch` 为准。 |

## 依赖

- 核心：`requirements.txt`（已有 requests 等）
- 抖音 ASR：`requirements-douyin.txt`（funasr / faster-whisper；Py 3.13+ 无 funasr）
- 系统：**ffmpeg**（提取 mp3；未安装时 funasr 尝试直接读 mp4）

## 配置

见 `.env.example` 中 `DOUYIN_*`。作品列表 API 需要浏览器 Cookie（`DOUYIN_COOKIE` 或 `secrets/douyin.cookie`）。
