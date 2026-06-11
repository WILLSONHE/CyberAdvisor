"""飞书 Bot 回复投递：内容类指令只发 .md 附件。"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime

from feishu.client import (
    reply_file,
    reply_text,
    send_file_to_chat,
    send_text_to_chat,
    upload_im_file,
)
from feishu.command_result import CommandResult
from feishu.env import FeishuConfig
from feishu.output_dir import resolve_feishu_output_dir

log = logging.getLogger("feishu.delivery")

# 帮助 / 连通 / Agent 提交确认等：短文本直发
TEXT_ONLY_EXACT = frozenset(
    {
        "help",
        "帮助",
        "?",
        "？",
        "ping",
        "测试",
        "test",
        "agent",
    }
)


def is_text_only_command(cmd: str, result: CommandResult) -> bool:
    if result.text_only:
        return True
    if result.agent_tasks:
        return True
    lower = cmd.strip().lower()
    if lower in TEXT_ONLY_EXACT:
        return True
    return False


def _safe_stem(text: str, *, max_len: int = 40) -> str:
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", text.strip())
    return stem[:max_len] or "reply"


def write_temp_md(content: str, stem: str) -> str:
    out_dir = resolve_feishu_output_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{_safe_stem(stem)}_{ts}.md")
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.rstrip())
        f.write("\n")
    return path


def _send_text(cfg: FeishuConfig, chat_id: str, message_id: str, text: str) -> None:
    if chat_id:
        send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, text)
    else:
        reply_text(cfg.app_id, cfg.app_secret, message_id, text)


def _send_file(cfg: FeishuConfig, chat_id: str, message_id: str, path: str, *, file_name: str) -> None:
    file_key = upload_im_file(
        cfg.app_id,
        cfg.app_secret,
        path,
        file_type="stream",
        file_name=file_name,
    )
    if chat_id:
        send_file_to_chat(cfg.app_id, cfg.app_secret, chat_id, file_key)
    else:
        reply_file(cfg.app_id, cfg.app_secret, message_id, file_key)


def remove_temp_file(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.remove(path)
            log.info("已删除临时文件 %s", path)
    except OSError as e:
        log.warning("删除临时文件失败 %s: %s", path, e)


def deliver_result(
    cfg: FeishuConfig,
    message_id: str,
    chat_id: str,
    cmd: str,
    result: CommandResult,
) -> None:
    """投递指令结果：内容类只发 .md 附件；帮助/错误等短文本直发。"""
    if is_text_only_command(cmd, result):
        if result.text:
            _send_text(cfg, chat_id, message_id, result.text)
        elif not result.file_path:
            _send_text(cfg, chat_id, message_id, "（无回复内容）")
        return

    temp_path = ""
    file_path = ""
    file_name = result.file_name or ""

    try:
        if result.file_path and os.path.isfile(result.file_path):
            file_path = result.file_path
            file_name = file_name or os.path.basename(file_path)
        elif result.text:
            stem = result.md_filename or _safe_stem(cmd)
            temp_path = write_temp_md(result.text, stem)
            file_path = temp_path
            file_name = file_name or os.path.basename(temp_path)
        else:
            _send_text(cfg, chat_id, message_id, "（无回复内容）")
            return

        _send_file(cfg, chat_id, message_id, file_path, file_name=file_name)
        log.info("已发送附件 %s", file_name)
    except Exception as e:
        log.exception("发送附件失败")
        err = f"附件发送失败：{e}"
        if result.text and len(result.text) < 800:
            err += f"\n\n{result.text}"
        _send_text(cfg, chat_id, message_id, err)
    finally:
        if temp_path:
            remove_temp_file(temp_path)
