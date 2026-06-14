"""飞书 Bot 异步 Cloud Agent 任务（产出仅写飞书 Temp，不写项目目录）。"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bilibili.env import apply_config_to_environ
from feishu.agent_prompts import (
    build_qry_prompt,
    build_sug_prompt,
    guess_stock_in_text,
    output_basename,
)
from feishu.client import (
    reply_text,
    send_text_to_chat,
    upload_im_file,
    reply_file,
    send_file_to_chat,
)
from feishu.delivery import remove_temp_file, write_temp_md
from feishu.text_util import split_reply
from feishu.env import FeishuConfig
from feishu.output_dir import resolve_feishu_output_dir

log = logging.getLogger("feishu.agent")

TEXT_CHUNK = 3500


@dataclass
class AgentTaskSpec:
    kind: str  # sug | qry | agent | graph_sug | graph_qry
    prompt: str = ""
    output_name: str = ""
    label: str = ""
    session: str | None = None
    sug_holder: str = ""  # sug：运行时再组装 prompt（含本机 vipdoc/模拟持仓抓取）
    user_request: str = ""  # agent 自由任务：运行时再组装 prompt（含本机行情抓取）
    graph_live: bool = False  # graph_sug：是否 force_live（须 GRAPH_PIPELINE_ENABLED=1）

    def resolve_prompt(self) -> str:
        if self.prompt:
            return self.prompt
        if self.kind == "sug" and self.sug_holder:
            return build_sug_prompt(self.sug_holder, session=self.session)
        if self.user_request:
            from feishu.agent_prompts import build_freeform_prompt

            return build_freeform_prompt(self.user_request)
        return ""


def agent_enabled() -> bool:
    apply_config_to_environ()
    if (os.environ.get("FEISHU_AGENT") or "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool((os.environ.get("CURSOR_API_KEY") or "").strip())


def _write_output(path: str, body: str, *, meta_header: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(meta_header)
        f.write("\n\n")
        f.write(body.strip())
        f.write("\n")


def _remove_output_file(path: str) -> None:
    """附件发送成功后删除本机临时 .md。"""
    try:
        if path and os.path.isfile(path):
            os.remove(path)
            log.info("已删除本机临时文件 %s", path)
    except OSError as e:
        log.warning("删除临时文件失败 %s: %s", path, e)


def _deliver_text(cfg: FeishuConfig, chat_id: str, message_id: str, text: str) -> None:
    for chunk in split_reply(text, TEXT_CHUNK):
        try:
            if chat_id:
                send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, chunk)
            else:
                reply_text(cfg.app_id, cfg.app_secret, message_id, chunk)
        except Exception as e:
            log.warning("发送文本失败: %s", e)
            if chat_id:
                send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, chunk)


def _deliver_file(cfg: FeishuConfig, chat_id: str, message_id: str, path: str) -> None:
    file_key = upload_im_file(
        cfg.app_id,
        cfg.app_secret,
        path,
        file_type="stream",
        file_name=os.path.basename(path),
    )
    if chat_id:
        send_file_to_chat(cfg.app_id, cfg.app_secret, chat_id, file_key)
    else:
        reply_file(cfg.app_id, cfg.app_secret, message_id, file_key)


def run_agent_task(cfg: FeishuConfig, message_id: str, chat_id: str, task: AgentTaskSpec) -> None:
    apply_config_to_environ()
    if task.kind in ("graph_sug", "graph_qry"):
        run_graph_agent_task(cfg, message_id, chat_id, task)
        return
    from ai_sim.agent_client import AgentClientError, run_analysis_prompt

    out_dir = resolve_feishu_output_dir()
    out_path = os.path.join(out_dir, task.output_name)
    prompt = task.resolve_prompt()
    if not prompt:
        _deliver_text(cfg, chat_id, message_id, f"❌ 任务无 prompt（{task.label}）")
        return
    log.info("Agent 任务开始 kind=%s label=%s out=%s", task.kind, task.label, out_path)

    try:
        resp = run_analysis_prompt(prompt)
    except AgentClientError as e:
        err = f"❌ Cloud Agent 失败（{task.label}）：{e}"
        log.exception("Agent 失败")
        _deliver_text(cfg, chat_id, message_id, err)
        return
    except Exception as e:
        log.exception("Agent 异常")
        _deliver_text(cfg, chat_id, message_id, f"❌ Cloud Agent 异常（{task.label}）：{e}")
        return

    body = (resp.get("result") or "").strip()
    if not body:
        _deliver_text(cfg, chat_id, message_id, f"❌ Cloud Agent 无输出（{task.label}）")
        return

    meta = (
        f"<!-- feishu-agent kind={task.kind} label={task.label} "
        f"agent={resp.get('agent_id', '')} -->"
    )
    _write_output(out_path, body, meta_header=meta)

    try:
        _deliver_file(cfg, chat_id, message_id, out_path)
    except Exception as e:
        log.warning("发送 .md 附件失败，改发临时文件: %s", e)
        fallback = write_temp_md(body, task.output_name.replace(".md", ""))
        try:
            _deliver_file(cfg, chat_id, message_id, fallback)
        except Exception as e2:
            _deliver_text(
                cfg,
                chat_id,
                message_id,
                f"⚠️ 附件发送失败（{e2}）",
            )
        finally:
            remove_temp_file(fallback)

    _remove_output_file(out_path)


def run_agent_tasks(
    cfg: FeishuConfig,
    message_id: str,
    chat_id: str,
    tasks: list[AgentTaskSpec],
) -> None:
    for i, task in enumerate(tasks, start=1):
        if len(tasks) > 1:
            _deliver_text(
                cfg,
                chat_id,
                message_id,
                f"📋 任务 {i}/{len(tasks)}：{task.label}…",
            )
        run_agent_task(cfg, message_id, chat_id, task)


def build_sug_tasks(holder: str, *, session: str | None = None) -> list[AgentTaskSpec]:
    if holder == "__ALL__":
        from portfolio_utils import load_holder_names

        names = load_holder_names()
        return [
            AgentTaskSpec(
                kind="sug",
                sug_holder=h,
                output_name=output_basename("sug", h, session=session),
                label=f"sug {h}" + (f" {session}" if session else ""),
                session=session,
            )
            for h in names
        ]
    return [
        AgentTaskSpec(
            kind="sug",
            sug_holder=holder,
            output_name=output_basename("sug", holder, session=session),
            label=f"sug {holder}" + (f" {session}" if session else ""),
            session=session,
        )
    ]


def build_qry_task(question: str) -> AgentTaskSpec:
    short = question[:30] + ("…" if len(question) > 30 else "")
    return AgentTaskSpec(
        kind="qry",
        prompt=build_qry_prompt(question),
        output_name=output_basename("qry", short.replace(" ", "_")),
        label=f"agent qry {short}",
    )


def build_freeform_task(user_request: str) -> AgentTaskSpec:
    code, name = guess_stock_in_text(user_request)
    if code and name and ("报告" in user_request or "分析" in user_request):
        slug = f"{name}_{code}_分析"
        label = f"agent {name} 分析报告"
    else:
        slug = user_request[:36].replace(" ", "_")
        label = f"agent {user_request[:40]}{'…' if len(user_request) > 40 else ''}"
    return AgentTaskSpec(
        kind="agent",
        user_request=user_request,
        output_name=output_basename("agent", slug),
        label=label,
    )


def graph_agent_enabled() -> bool:
    apply_config_to_environ()
    try:
        from graph.llm import graph_pipeline_enabled

        return graph_pipeline_enabled() and agent_enabled()
    except Exception:
        return False


def build_graph_sug_tasks(holder: str, *, session: str | None = None) -> list[AgentTaskSpec]:
    base = build_sug_tasks(holder, session=session)
    out: list[AgentTaskSpec] = []
    for t in base:
        out.append(
            AgentTaskSpec(
                kind="graph_sug",
                sug_holder=t.sug_holder,
                output_name=t.output_name.replace("_sug", "_graph_sug"),
                label=t.label.replace("sug", "graph sug"),
                session=t.session,
                graph_live=True,
            )
        )
    return out


def build_graph_qry_task(question: str) -> AgentTaskSpec:
    short = question[:30] + ("…" if len(question) > 30 else "")
    return AgentTaskSpec(
        kind="graph_qry",
        prompt=question,
        output_name=output_basename("graph_qry", short.replace(" ", "_")),
        label=f"graph qry {short}",
        graph_live=True,
    )


def run_graph_agent_task(cfg: FeishuConfig, message_id: str, chat_id: str, task: AgentTaskSpec) -> None:
    from graph.llm import graph_pipeline_enabled
    from graph.orchestrator import run_qry_pipeline, run_sug_pipeline

    if not graph_pipeline_enabled():
        _deliver_text(
            cfg,
            chat_id,
            message_id,
            "❌ Graph 管线未启用。开发已完成；设置 `GRAPH_PIPELINE_ENABLED=1` 后再试 "
            "（默认仍走 `agent sug` 单 Agent）。",
        )
        return

    out_dir = resolve_feishu_output_dir()
    out_path = os.path.join(out_dir, task.output_name)
    log.info("Graph 任务开始 kind=%s label=%s", task.kind, task.label)

    try:
        if task.kind == "graph_sug":
            state = run_sug_pipeline(
                task.sug_holder,
                session=task.session,
                dry_run=False,
                force_live=task.graph_live,
            )
        else:
            state = run_qry_pipeline(task.prompt, dry_run=False, force_live=task.graph_live)
    except Exception as e:
        log.exception("Graph 失败")
        _deliver_text(cfg, chat_id, message_id, f"❌ Graph 管线失败（{task.label}）：{e}")
        return

    body = (state.final_markdown or "").strip()
    if not body:
        _deliver_text(cfg, chat_id, message_id, f"❌ Graph 无输出（{task.label}）")
        return

    meta = (
        f"<!-- feishu-graph analysis_id={state.analysis_id} "
        f"spent_usd={state.budget.spent_usd:.2f} dry_run={state.dry_run} -->"
    )
    _write_output(out_path, body, meta_header=meta)

    summary = (
        f"✅ Graph 完成 `{state.analysis_id}` · "
        f"${state.budget.spent_usd:.2f}/{state.budget.cap_usd:.2f} · "
        f"{state.budget.llm_calls} calls"
    )
    _deliver_text(cfg, chat_id, message_id, summary)

    try:
        _deliver_file(cfg, chat_id, message_id, out_path)
    except Exception as e:
        log.warning("Graph 附件失败: %s", e)
        fallback = write_temp_md(body, task.output_name.replace(".md", ""))
        try:
            _deliver_file(cfg, chat_id, message_id, fallback)
        finally:
            remove_temp_file(fallback)

    _remove_output_file(out_path)
