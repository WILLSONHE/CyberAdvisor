"""Cursor Cloud Agents API 客户端（无 repo 分析模式 + 可选 GitHub repo）。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

API_BASE = "https://api.cursor.com/v1"


class AgentClientError(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _api_key() -> str:
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        raise AgentClientError("未设置 CURSOR_API_KEY（Cursor Dashboard → Integrations）")
    return key


def _request(method: str, path: str, body: dict | None = None, *, timeout: int = 120) -> dict:
    url = f"{API_BASE}{path}"
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    import base64

    token = base64.b64encode(f"{_api_key()}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        retryable = e.code in (429, 500, 502, 503, 504)
        raise AgentClientError(f"HTTP {e.code}: {detail[:500]}", retryable=retryable) from e
    except urllib.error.URLError as e:
        raise AgentClientError(f"网络错误: {e.reason}", retryable=True) from e


def _github_default_branch(owner: str, repo: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return str(data.get("default_branch") or "") or None
    except Exception:
        return None


def resolve_starting_ref(repo: str, *, fallback: str = "main") -> str:
    """CURSOR_CLOUD_REF → GitHub default_branch → fallback。"""
    explicit = (os.environ.get("CURSOR_CLOUD_REF") or "").strip()
    if explicit:
        return explicit
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo, re.I)
    if not m:
        owner_repo = repo.lstrip("/")
        if "/" in owner_repo and not owner_repo.startswith("http"):
            parts = owner_repo.split("/", 1)
            detected = _github_default_branch(parts[0], parts[1].removesuffix(".git"))
            return detected or fallback
        return fallback
    detected = _github_default_branch(m.group(1), m.group(2).removesuffix(".git"))
    return detected or fallback


def create_cloud_run(
    prompt_text: str,
    *,
    model_id: str = "composer-2.5",
    repo_url: str = "",
    starting_ref: str = "",
) -> tuple[str, str]:
    """创建 Cloud Agent 并返回 (agent_id, run_id)。"""
    body: dict[str, Any] = {
        "prompt": {"text": prompt_text},
        "model": {"id": model_id},
        "mode": "agent",
        "skipReviewerRequest": True,
    }
    repo = (repo_url or os.environ.get("CURSOR_CLOUD_REPO") or "").strip()
    if repo:
        if not repo.startswith("http"):
            repo = f"https://github.com/{repo.lstrip('/')}"
        branch = resolve_starting_ref(repo, fallback=starting_ref or "main")
        body["repos"] = [{"url": repo, "startingRef": branch}]
        body["workOnCurrentBranch"] = True

    resp = _request("POST", "/agents", body)
    agent = resp.get("agent") or {}
    run = resp.get("run") or {}
    agent_id = agent.get("id") or ""
    run_id = run.get("id") or agent.get("latestRunId") or ""
    if not agent_id or not run_id:
        raise AgentClientError(f"创建 Agent 失败: {resp!r}")
    return agent_id, run_id


def poll_run(agent_id: str, run_id: str, *, timeout_s: float = 600, interval_s: float = 5.0) -> dict:
    """轮询直至 run 终止，返回 run 对象（含 result）。"""
    deadline = time.time() + timeout_s
    terminal = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}
    while time.time() < deadline:
        run = _request("GET", f"/agents/{agent_id}/runs/{run_id}", timeout=60)
        status = (run.get("status") or "").upper()
        if status in terminal:
            return run
        time.sleep(interval_s)
    raise AgentClientError(f"Agent 超时（>{timeout_s:.0f}s）: {run_id}", retryable=True)


def run_analysis_prompt(prompt_text: str) -> dict[str, Any]:
    """一次性 Cloud Agent 分析，返回 {agent_id, run_id, status, result, duration_ms}。"""
    agent_id, run_id = create_cloud_run(prompt_text)
    run = poll_run(
        agent_id,
        run_id,
        timeout_s=float(os.environ.get("AI_SIM_AGENT_TIMEOUT", "600")),
    )
    return {
        "agent_id": agent_id,
        "run_id": run_id,
        "status": run.get("status"),
        "result": run.get("result") or "",
        "duration_ms": run.get("durationMs"),
        "url": f"https://cursor.com/agents/{agent_id}",
    }