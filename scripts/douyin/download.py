"""从抖音下载视频/音频（iesdouyin 路线，无需登录；基于 External_Skills/douyin-transcribe）。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
ROUTER_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.DOTALL)

_DOWNLOAD_HEADERS = {
    "User-Agent": MOBILE_UA,
    "Referer": "https://www.douyin.com/",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_CURL = shutil.which("curl.exe") or shutil.which("curl")


def _download_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(_DOWNLOAD_HEADERS)
    return session


def extract_video_id(url_or_id: str) -> str:
    """从短链/完整链接/纯 ID 提取 aweme_id。"""
    text = (url_or_id or "").strip()
    if text.isdigit():
        return text
    if "v.douyin.com" in text:
        with _download_session() as session:
            resp = session.head(text, allow_redirects=True, timeout=20)
        text = resp.url
    m = re.search(r"/video/(\d+)", text)
    if m:
        return m.group(1)
    raise ValueError(f"无法从链接解析 aweme_id: {url_or_id}")


def _fetch_router_data(video_id: str) -> dict:
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with _download_session() as session:
                share_url = f"https://www.iesdouyin.com/share/video/{video_id}"
                resp = session.get(share_url, timeout=30)
                resp.raise_for_status()
            match = ROUTER_RE.search(resp.text)
            if not match:
                raise RuntimeError(f"未找到 _ROUTER_DATA: {video_id}")
            data = json.loads(match.group(1).strip())
            loader = data.get("loaderData") or {}
            page = loader.get("video_(id)/page") or loader.get("video_id/page") or {}
            info = page.get("videoInfoRes") or {}
            items = info.get("item_list") or []
            if not items:
                raise RuntimeError(f"视频不存在或已下架: {video_id}")
            return items[0]
        except (requests.RequestException, RuntimeError) as e:
            last_err = e
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"获取视频元数据失败: {video_id}") from last_err


def _video_urls(item: dict) -> list[str]:
    """收集 play_addr + bit_rate 备用链（去重）。"""
    video = item.get("video") or {}
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        url = raw.replace("playwm", "play")
        if url and url not in seen:
            seen.add(url)
            out.append(url)

    for raw in (video.get("play_addr") or {}).get("url_list") or []:
        add(raw)
    for br in video.get("bit_rate") or []:
        for raw in (br.get("play_addr") or {}).get("url_list") or []:
            add(raw)
    return out


def _download_curl(url: str, dest: str) -> None:
    if not _CURL:
        raise RuntimeError("未找到 curl.exe")
    if os.path.exists(dest):
        os.remove(dest)
    cmd = [
        _CURL,
        "-L",
        "--retry",
        "5",
        "--retry-delay",
        "2",
        "--connect-timeout",
        "20",
        "--max-time",
        "600",
        "-o",
        dest,
        "-H",
        f"User-Agent: {MOBILE_UA}",
        "-H",
        "Referer: https://www.douyin.com/",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=620)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-300:]
        raise RuntimeError(f"curl 下载失败 (code={proc.returncode}): {tail}")
    if not os.path.isfile(dest) or os.path.getsize(dest) < 10_000:
        raise RuntimeError("curl 下载文件过小")


def _download_requests(url: str, dest: str) -> None:
    if os.path.exists(dest):
        os.remove(dest)
    with _download_session() as session:
        with session.get(url, timeout=(20, 300), stream=True) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
    if os.path.getsize(dest) < 10_000:
        raise RuntimeError("下载文件过小")


def _download_to_file(url: str, dest: str, *, attempts: int = 3) -> None:
    """Windows 优先 curl.exe（比 requests 更稳）；失败再 requests。"""
    last_err: Exception | None = None
    backends: list[str] = ["curl", "requests"] if _CURL else ["requests"]
    for attempt in range(attempts):
        for backend in backends:
            try:
                if backend == "curl":
                    _download_curl(url, dest)
                else:
                    _download_requests(url, dest)
                return
            except Exception as e:
                last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"CDN 下载失败（已重试 {attempts} 次）: {url[:80]}…") from last_err


def download_video(
    video_id: str,
    output_dir: str,
    *,
    on_status: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """下载 mp4，返回 (video_path, title)。每次尝试重新拉元数据（CDN 签名有时效）。"""
    os.makedirs(output_dir, exist_ok=True)
    video_path = os.path.join(output_dir, f"{video_id}.mp4")
    title = video_id

    errors: list[str] = []
    for round_i in range(3):
        item = _fetch_router_data(video_id)
        title = item.get("desc") or title
        urls = _video_urls(item)
        if not urls:
            raise RuntimeError(f"无可用下载链接: {video_id}")
        if on_status and round_i == 0:
            on_status(f"下载视频: {title[:50]}…")
        for i, url in enumerate(urls):
            try:
                _download_to_file(url, video_path)
                return video_path, title
            except Exception as e:
                errors.append(f"r{round_i + 1}/cdn{i + 1}: {e}")
        time.sleep(2.0 * (round_i + 1))
    raise RuntimeError(f"全部 CDN 均失败 ({video_id}): " + " | ".join(errors[-4:]))


def extract_audio(video_path: str, output_dir: str | None = None) -> str:
    """ffmpeg 提取 mp3；若无 ffmpeg 则返回原 mp4 路径供 ASR 直接读取。"""
    output_dir = output_dir or os.path.dirname(video_path)
    audio_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}.mp3")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return video_path
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ab",
            "128k",
            audio_path,
        ],
        capture_output=True,
        timeout=120,
        check=True,
    )
    if os.path.isfile(audio_path):
        try:
            os.remove(video_path)
        except OSError:
            pass
        return audio_path
    return video_path


def download_audio(
    video_id: str,
    output_dir: str | None = None,
    *,
    on_status: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """下载并提取音频，返回 (audio_path, title)。"""
    output_dir = output_dir or tempfile.mkdtemp(prefix="dyt-")
    video_path, title = download_video(video_id, output_dir, on_status=on_status)
    audio_path = extract_audio(video_path, output_dir)
    return audio_path, title
