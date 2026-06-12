---
name: douyin-transcribe
description: >
  抖音（fetch tiktok）视频文稿抓取：钱加贝等博主 → SenseVoice 转录 → Raw/未审阅视频文稿。
  批量用 scripts/douyin_fetch.py；单链可用 scripts/douyin/download.py + transcribe.py。
  触发词：fetch tiktok、抖音转录、钱加贝、douyin_fetch。
category: media
---

# 抖音 / fetch tiktok

> 源技能：`External_Skills/Transcribe_Skills/douyin-transcribe`（只读，已消化到 `scripts/douyin/`）

## 流水线

```
douyin_fetch.py → Raw/未审阅视频文稿/ → rw_video.py → txtcfm → ing（或 video_ingest_batch.py 批量）
```

与 B 站相同；B 站用 API 字幕，抖音用 **ASR**（SenseVoice 或 faster-whisper）。

## 命令

```bash
cd scripts
python douyin_fetch.py              # 默认近 180 天增量
python douyin_fetch.py --dry-run
python douyin_fetch.py --since 2025-12-11
python tiktok_fetch.py              # 别名
```

## 配置（.env）

- `DOUYIN_SEC_UID` — 博主 sec_uid（默认钱加贝）
- `DOUYIN_CREATOR` — 显示名
- `DOUYIN_COOKIE` — 浏览器 Cookie（列表 API 必填）；或写入 `secrets/douyin.cookie`

## 依赖

```bash
pip install -r requirements-douyin.txt
# ffmpeg（winget install Gyan.FFmpeg）
```

## 与 bilibili-transcribe 差异

| | B 站 (`bilibili_fetch`) | 抖音 (`douyin_fetch`) |
|--|--|--|
| 文本来源 | 官方字幕 API | ASR（SenseVoice ≤Py3.12；faster-whisper 3.13+） |
| 登录 | B 站 Cookie | 抖音 Cookie（仅列表） |
| 单视频下载 | — | iesdouyin，无需 Cookie |

详见 `EXTERNAL_SKILLS.md`。
