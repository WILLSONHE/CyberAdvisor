"""飞书 Bot 指令路由（本地读 + `agent` 前缀触发 Cloud Agent）。"""
from __future__ import annotations

import os
import re

from bilibili.env import ROOT
from portfolio_utils import (
    filter_pool_md,
    filter_portfolio_md,
    format_hint,
    latest_sug_path,
    load_holder_names,
    parse_holder_arg,
    parse_sug_command,
    sug_archive_basename,
)
from feishu.agent_jobs import agent_enabled, build_freeform_task, build_qry_task, build_sug_tasks
from feishu.command_result import CommandResult
from feishu.wiki_local import WIKI_ROOT, build_wiki_tree, find_wiki_md
from sim_portfolio import handle_sim_command
from wiki import run_chk, search_wiki, track_stock
from wiki.common import format_hint as wiki_format_hint
from wiki.common import parse_tail_arg

from feishu.text_util import encoding_damage_note, read_text_file

SUG_VERBS = ("sug", "交易策略", "开仓")
SIM_PREFIX = "sim"
HOLDING_VERBS = ("持仓", "portfolio")
POOL_VERBS = ("日报", "pool", "标的池")
TRK_VERBS = ("trk", "追踪", "track")
CHK_VERBS = ("chk", "体检", "check")
QRY_VERBS = ("qry", "问", "query")

AGENT_PREFIX_RE = re.compile(r"^agent\s+(.+)$", re.IGNORECASE)
AGENT_QRY_RE = re.compile(r"^(?:qry|问|query)\s+(.+)$", re.IGNORECASE)

OPEN_RE = re.compile(r"^打开\s+(.+)$", re.IGNORECASE)


def _text_result(text: str) -> CommandResult:
    return CommandResult.from_text(text)


def _md_result(body: str, *, filename: str) -> CommandResult:
    return CommandResult.from_markdown(body, filename=filename)


def _agent_disabled_message() -> str:
    return (
        "Cloud Agent 未启用。请在项目根 `.env` 配置 `CURSOR_API_KEY`（Cursor Dashboard → Integrations），"
        "并确认 `FEISHU_AGENT` 不为 0，然后重启 feishu_bot.bat。"
    )


def _agent_ack(label: str, *, extra: str = "") -> str:
    base = (
        f"⏳ 已提交 **{label}**（Cloud Agent），预计 3–10 分钟。\n"
        f"完成后以 **.md 附件** 发到本会话（发送后本机临时文件自动删除），**不写入** SugVault/Wiki。"
    )
    return f"{base}\n{extra}".strip()


def _handle_wiki_tree() -> CommandResult:
    tree = build_wiki_tree()
    body = (
        "Wiki 目录（`每日复盘/`、`视频专题/` 仅显示文件夹摘要，不列文件）\n\n"
        + tree
        + "\n\n---\n\n示例：`打开 仓位管理` · `打开 每日复盘/2026-06-12`"
    )
    return _md_result(body, filename="wiki目录")


def _handle_open_wiki(query: str) -> CommandResult:
    matches = find_wiki_md(query)
    if not matches:
        return _text_result(
            f"未找到 Wiki 文件：{query}\n"
            "发送「策略文件」查看目录；示例：打开 仓位管理 / 打开 每日复盘/2026-06-05"
        )
    if len(matches) > 1:
        lines = [f"「{query}」匹配到多个文件，请更精确："]
        for p in matches[:15]:
            rel = os.path.relpath(p, WIKI_ROOT).replace("\\", "/")
            lines.append(f"• 打开 {rel}")
        if len(matches) > 15:
            lines.append(f"… 共 {len(matches)} 个")
        return _text_result("\n".join(lines))

    md_path = matches[0]
    return CommandResult.from_existing_file(str(md_path), file_name=md_path.name)


def _read_sug_body(holder: str, session: str | None) -> str:
    path = latest_sug_path(holder, session)
    if not path:
        return ""
    text, damaged = read_text_file(path)
    if damaged:
        text = encoding_damage_note(holder=holder, session=session) + text
    return text


def _sug_missing_message(holder: str, session: str | None) -> str:
    example = f"agent sug {holder}"
    if session:
        example += f" {session}"
    read_example = f"sug {holder}"
    if session:
        read_example += f" {session}"
    fname = sug_archive_basename(holder, session)
    return (
        f"尚无 {holder} 的 sug 报告"
        f"{f'（{session}）' if session else ''}。"
        f"发送「{example}」由 Cloud Agent 生成，或在 Cursor 生成后写入 SugVault/{fname}。"
        f"若已有归档，发送「{read_example}」读取。"
    )


def _handle_sug_command(text: str) -> CommandResult | None:
    parsed = parse_sug_command(text)
    if parsed is None:
        return None
    holder, session, err = parsed
    if err:
        return _text_result(err)
    assert holder is not None

    if holder == "__ALL__":
        names = load_holder_names()
        if not names:
            return _text_result("尚无持仓数据，请先运行 daily.bat 同步 持仓.xlsx")
        blocks: list[str] = []
        for h in names:
            body = _read_sug_body(h, session)
            if not body:
                body = _sug_missing_message(h, session)
            blocks.append(f"# {h}\n\n{body}")
        sess = session or "当日"
        return _md_result("\n\n---\n\n".join(blocks), filename=f"sug_全员_{sess}")

    path = latest_sug_path(holder, session)
    if path:
        return CommandResult.from_existing_file(path, file_name=os.path.basename(path))
    return _text_result(_sug_missing_message(holder, session))


def _handle_agent_sug(rest: str) -> CommandResult:
    parsed = parse_sug_command(rest)
    if parsed is None:
        return _text_result("用法：agent sug {持有人} [早盘|午盘] | agent sug 全员 [早盘|午盘]")
    holder, session, err = parsed
    if err:
        return _text_result(err)
    assert holder is not None

    tasks = build_sug_tasks(holder, session=session)
    if holder == "__ALL__":
        ack = _agent_ack(
            f"sug 全员{f' {session}' if session else ''} × {len(tasks)}",
            extra="完成后每位持有人各一份 .md 附件。",
        )
    else:
        label = f"sug {holder}" + (f" {session}" if session else "")
        ack = _agent_ack(label)
    return CommandResult.async_agent(ack, tasks)


def _handle_agent_command(text: str) -> CommandResult | None:
    stripped = text.strip()
    if stripped.lower() == "agent":
        return _text_result(
            "Cloud Agent 用法（须前缀 agent）：\n"
            "• agent sug {持有人} [早盘|午盘]\n"
            "• agent sug 全员 [早盘|午盘]\n"
            "• agent qry {问题}\n"
            "• agent 给我一份新易盛的分析报告\n\n"
            "普通 sug / qry 仍为本地读 SugVault / Wiki 检索（.md 附件）。"
        )

    m = AGENT_PREFIX_RE.match(stripped)
    if not m:
        return None

    if not agent_enabled():
        return _text_result(_agent_disabled_message())

    rest = m.group(1).strip()
    if not rest:
        return _text_result("请在 agent 后输入任务，例如：agent sug Wilson 午盘")

    if parse_sug_command(rest) is not None:
        return _handle_agent_sug(rest)

    qm = AGENT_QRY_RE.match(rest)
    if qm:
        question = qm.group(1).strip()
        if not question:
            return _text_result("用法：agent qry {你的问题}")
        task = build_qry_task(question)
        return CommandResult.async_agent(_agent_ack(task.label), [task])

    task = build_freeform_task(rest)
    return CommandResult.async_agent(_agent_ack(task.label), [task])


def _handle_tail_command(text: str, verbs: tuple[str, ...], handler, *, arg_label: str) -> str | None:
    parsed = parse_tail_arg(text, verbs)
    if parsed is None:
        return None
    arg, err = parsed
    if err:
        return err
    assert arg is not None
    return handler(arg)


def _handle_holder_command(text: str, verbs: tuple[str, ...], handler) -> str | None:
    parsed = parse_holder_arg(text, verbs)
    if parsed is None:
        return None
    holder, err = parsed
    if err:
        return err
    assert holder is not None
    return handler(holder)


def handle_command(text: str) -> CommandResult:
    cmd = text.strip()
    lower = cmd.lower()

    if lower in ("help", "帮助", "?", "？"):
        names_hint = ""
        try:
            names = load_holder_names()
            if names:
                names_hint = f"\n当前持有人：{', '.join(names)}"
        except Exception:
            pass
        return _text_result(
            "CyberAdvisor 飞书 Bot（本机）\n\n"
            "【Cloud Agent · 须前缀 agent】\n"
            "• agent sug {持有人} [早盘|午盘] — 异步生成 sug（.md 附件）\n"
            "• agent sug 全员 [早盘|午盘]\n"
            "• agent qry {问题} — 深度 Wiki 作答\n"
            "• agent {自由任务} — 如：agent 给我一份新易盛的分析报告\n\n"
            "【持仓 / 交易 · 本地读 → .md 附件】\n"
            "• sug {持有人} [早盘|午盘] — SugVault 已有报告\n"
            "• sug 全员 [早盘|午盘]\n"
            "• 持仓 {持有人} | 标的池 {持有人}\n"
            "• sim 买/卖 …\n\n"
            "【Wiki 查询 → .md 附件】\n"
            "• 策略文件 | 打开 {路径}\n"
            "• trk {标的} | chk | qry {关键词}\n\n"
            "• ping — 连通测试\n\n"
            f"示例：agent sug 全员 午盘 / sug Wilson / qry 存储{names_hint}\n\n"
            "ing / rw / txtcfm → Cursor + SKILL.md。"
        )

    if lower in ("ping", "测试", "test"):
        return _text_result("pong — CyberAdvisor Bot 在线")

    agent_reply = _handle_agent_command(cmd)
    if agent_reply is not None:
        return agent_reply

    if lower in ("策略文件", "wiki目录", "wiki 目录", "wiki tree"):
        return _handle_wiki_tree()

    open_m = OPEN_RE.match(cmd)
    if open_m:
        return _handle_open_wiki(open_m.group(1).strip())

    if lower.startswith(SIM_PREFIX):
        reply = handle_sim_command(cmd)
        if reply is not None:
            return _md_result(reply, filename="sim")
        return _text_result("sim 指令格式：sim 买 利通电子，江波龙 / sim 卖 利通电子")

    if lower in CHK_VERBS:
        return _md_result(run_chk(), filename="chk")

    reply = _handle_tail_command(cmd, TRK_VERBS, track_stock, arg_label="标的")
    if reply is not None:
        return _md_result(reply, filename=f"trk_{cmd.split()[-1]}")

    reply = _handle_tail_command(cmd, QRY_VERBS, search_wiki, arg_label="问题")
    if reply is not None:
        return _md_result(reply, filename="qry")

    reply = _handle_sug_command(cmd)
    if reply is not None:
        return reply

    reply = _handle_holder_command(
        cmd,
        HOLDING_VERBS,
        lambda holder: filter_portfolio_md(holder),
    )
    if reply is not None:
        return _md_result(reply, filename=f"持仓_{cmd.split()[-1]}")

    reply = _handle_holder_command(
        cmd,
        POOL_VERBS,
        lambda holder: filter_pool_md(holder),
    )
    if reply is not None:
        return _md_result(reply, filename=f"标的池_{cmd.split()[-1]}")

    if lower in SUG_VERBS:
        return _text_result(format_hint("sug"))
    if lower in HOLDING_VERBS:
        return _text_result(format_hint("持仓"))
    if lower in POOL_VERBS:
        return _text_result(format_hint("标的池"))
    if lower in TRK_VERBS:
        return _text_result(wiki_format_hint("trk", "标的"))
    if lower in QRY_VERBS:
        return _text_result(wiki_format_hint("qry", "问题"))

    return _text_result(
        f"未识别指令：{cmd}\n"
        "发送「帮助」查看可用指令；Cloud Agent 任务请以 agent 开头。"
    )
