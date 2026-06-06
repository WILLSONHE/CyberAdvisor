"""校验 .env 中 CURSOR_API_KEY / CURSOR_CLOUD_REPO 配置（不打印密钥）。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def load_dotenv() -> None:
    from bilibili.env import apply_config_to_environ

    apply_config_to_environ()


def normalize_repo(raw: str) -> tuple[str, str, str]:
    """返回 (owner, repo, https_url)。"""
    s = raw.strip().rstrip("/")
    if not s:
        raise ValueError("CURSOR_CLOUD_REPO 为空")
    if s.startswith("http"):
        m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s, re.I)
        if not m:
            raise ValueError(f"无法解析 GitHub URL：{s}")
        owner, repo = m.group(1), m.group(2)
        return owner, repo, f"https://github.com/{owner}/{repo}"
    if "/" not in s:
        raise ValueError(f"格式应为 owner/repo 或完整 GitHub URL，当前：{s!r}")
    owner, repo = s.split("/", 1)
    owner, repo = owner.strip(), repo.strip().removesuffix(".git")
    if not owner or not repo:
        raise ValueError(f"格式应为 owner/repo，当前：{s!r}")
    return owner, repo, f"https://github.com/{owner}/{repo}"


def check_github_repo(owner: str, repo: str) -> tuple[bool, str, str]:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        vis = "私有" if data.get("private") else "公开"
        default_branch = str(data.get("default_branch") or "main")
        return (
            True,
            f"GitHub 仓库存在（{vis}）default_branch={default_branch}",
            default_branch,
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "GitHub 返回 404：仓库不存在或当前网络/账号不可见（私有库需 Cursor 能访问）", "main"
        return False, f"GitHub HTTP {e.code}", "main"
    except urllib.error.URLError as e:
        return False, f"无法访问 GitHub：{e.reason}", "main"


def check_gh_cli(owner: str, repo: str) -> tuple[bool | None, str]:
    try:
        r = subprocess.run(
            ["gh", "repo", "view", f"{owner}/{repo}", "--json", "nameWithOwner,visibility,defaultBranchRef"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        return None, "未安装 gh CLI（可跳过）"
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:200]
        return False, f"gh repo view 失败：{err or 'unknown'}"
    try:
        data = json.loads(r.stdout)
        vis = data.get("visibility", "?")
        branch = (data.get("defaultBranchRef") or {}).get("name", "?")
        return True, f"gh 可访问 {data.get('nameWithOwner')}（{vis}）默认分支 {branch}"
    except json.JSONDecodeError:
        return True, "gh 可访问该仓库"


def check_cursor_api_key() -> tuple[bool, str]:
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        return False, "未设置 CURSOR_API_KEY"
    import base64

    req = urllib.request.Request(
        "https://api.cursor.com/v1/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    token = base64.b64encode(f"{key}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        n = len(data.get("models") or data if isinstance(data, list) else [])
        if isinstance(data, dict) and "models" in data:
            n = len(data["models"])
        elif isinstance(data, list):
            n = len(data)
        return True, f"CURSOR_API_KEY 有效（模型列表 {n} 项）"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return False, f"Cursor API HTTP {e.code}：{body}"
    except urllib.error.URLError as e:
        return False, f"无法连接 Cursor API：{e.reason}"


def check_repo_agent_dry(owner: str, repo: str, url: str, *, branch: str) -> tuple[bool | None, str]:
    """可选：发起最小 Cloud Agent 请求验证 repo 被 Cursor 接受（会消耗少量配额）。"""
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        return None, "跳过（无 API Key）"
    import base64

    body = {
        "prompt": {"text": 'Reply with exactly: {"ok":true}'},
        "model": {"id": "composer-2.5"},
        "mode": "agent",
        "skipReviewerRequest": True,
        "repos": [{"url": url, "startingRef": branch}],
        "workOnCurrentBranch": True,
    }
    req = urllib.request.Request(
        "https://api.cursor.com/v1/agents",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    token = base64.b64encode(f"{key}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        agent = (data.get("agent") or {}).get("id", "")
        repos = (data.get("agent") or {}).get("repos") or []
        if repos:
            return True, f"Cursor 已接受仓库配置 agent={agent}"
        return True, f"Agent 已创建 agent={agent}（请打开 Cursor 控制台确认 clone 无报错）"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        return False, f"Cursor 拒绝创建 Agent（HTTP {e.code}）：{detail}"
    except urllib.error.URLError as e:
        return False, f"请求失败：{e.reason}"


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="校验 CURSOR_CLOUD_REPO 与 CURSOR_API_KEY")
    ap.add_argument("--live", action="store_true", help="向 Cursor 发起一次最小 Agent 请求（消耗配额）")
    args = ap.parse_args()

    load_dotenv()
    ok_all = True

    print(f"项目根目录：{ROOT}")
    print()

    api_ok, api_msg = check_cursor_api_key()
    print(f"[{'OK' if api_ok else 'FAIL'}] {api_msg}")
    ok_all &= api_ok

    raw = (os.environ.get("CURSOR_CLOUD_REPO") or "").strip()
    if not raw:
        print("[SKIP] 未设置 CURSOR_CLOUD_REPO（可选；不设置则 Agent 仅依赖 prompt 内嵌数据）")
        return 0 if ok_all else 1

    try:
        owner, repo, url = normalize_repo(raw)
        print(f"[OK] 格式解析 → {owner}/{repo}")
        print(f"     Cursor 将使用 URL：{url}")
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 1

    gh_ok, gh_msg = check_gh_cli(owner, repo)
    if gh_ok is None:
        print(f"[SKIP] {gh_msg}")
    else:
        print(f"[{'OK' if gh_ok else 'FAIL'}] {gh_msg}")
        ok_all &= gh_ok

    gh_api_ok, gh_api_msg, default_branch = check_github_repo(owner, repo)
    print(f"[{'OK' if gh_api_ok else 'WARN'}] {gh_api_msg}")
    env_ref = (os.environ.get("CURSOR_CLOUD_REF") or "").strip()
    use_branch = env_ref or default_branch
    if env_ref:
        print(f"[OK] CURSOR_CLOUD_REF={env_ref}")
    else:
        print(f"[OK] 将使用 GitHub 默认分支：{use_branch}")
    if not gh_api_ok and gh_ok is not True:
        ok_all = False

    if args.live:
        print()
        print(f"正在向 Cursor 发起 live 检测（分支 {use_branch}，约 1–2 分钟）…")
        live_ok, live_msg = check_repo_agent_dry(owner, repo, url, branch=use_branch)
        if live_ok is None:
            print(f"[SKIP] {live_msg}")
        else:
            print(f"[{'OK' if live_ok else 'FAIL'}] {live_msg}")
            ok_all &= live_ok

    print()
    if ok_all:
        print("结论：配置看起来正确。完整验证可再跑：.\\ai_sim_tick.bat --force")
    else:
        print("结论：存在问题，请按上方 FAIL 项修正 .env")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
