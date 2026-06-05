"""飞书 Bot 事件回调 HTTP 服务（本机运行，需公网 URL 或内网穿透）。"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from bilibili.env import ROOT
from feishu.client import (
    reply_file,
    reply_text,
    send_file_to_chat,
    send_text_to_chat,
    upload_im_file,
)
from feishu.commands import handle_command, split_reply
from feishu.decrypt import decrypt_event
from feishu.env import FeishuConfig

log = logging.getLogger("feishu.bot")
DEBUG_LOG = os.path.join(ROOT, "Wiki", "数据", "feishu_debug.log")


def _debug_log(label: str, data: str) -> None:
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n=== {stamp} {label} ===\n{data}\n")
    except OSError:
        pass


def _read_post_bytes(handler: BaseHTTPRequestHandler) -> bytes:
    cl = handler.headers.get("Content-Length")
    if cl is not None:
        n = int(cl)
        if n > 0:
            return handler.rfile.read(n)
        return b""
    # 部分客户端不带 Content-Length
    return handler.rfile.read(1024 * 1024)


def _parse_body(raw_bytes: bytes, cfg: FeishuConfig) -> dict | None:
    if not raw_bytes:
        return {}
    for enc in ("utf-8", "utf-8-sig"):
        try:
            raw = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            raw = None
    else:
        raw = raw_bytes.decode("utf-8", errors="replace")

    raw = raw.strip()
    if not raw:
        return {}

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        # 极少数情况下整段 body 就是密文
        if cfg.encrypt_key:
            try:
                return decrypt_event(cfg.encrypt_key, raw)
            except Exception as e:
                log.error("密文直解失败: %s", e)
        _debug_log("JSON_PARSE_FAIL", repr(raw[:2000]))
        return None

    if isinstance(body, dict) and body.get("encrypt"):
        if not cfg.encrypt_key:
            log.error("飞书开启了事件加密，请在 .env 配置 FEISHU_ENCRYPT_KEY（事件订阅页的 Encrypt Key）")
            _debug_log("ENCRYPT_NO_KEY", json.dumps(body, ensure_ascii=False)[:500])
            return {"_encrypt_only": True}
        try:
            return decrypt_event(cfg.encrypt_key, body["encrypt"])
        except Exception as e:
            log.exception("解密失败")
            _debug_log("DECRYPT_FAIL", str(e))
            return None
    return body


def _parse_message_content(raw: str) -> str:
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            text = obj.get("text") or obj.get("title") or ""
            if text:
                return str(text).strip()
            # 群聊 @ 机器人常见 post 富文本
            content = obj.get("content")
            if isinstance(content, list):
                parts: list[str] = []
                for row in content:
                    if not isinstance(row, list):
                        continue
                    for cell in row:
                        if not isinstance(cell, dict):
                            continue
                        tag = cell.get("tag")
                        if tag == "text":
                            parts.append(str(cell.get("text", "")))
                        elif tag == "at":
                            parts.append(" ")
                joined = "".join(parts).strip()
                if joined:
                    return joined
            if "content" in obj and isinstance(obj.get("content"), str):
                return str(obj.get("content", "")).strip()
    except json.JSONDecodeError:
        pass
    return str(raw).strip()


def _clean_command_text(text: str) -> str:
    text = re.sub(r"<at[^>]*>|</at>", "", text)
    text = text.replace("@_user_1", "").replace("@_all", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _handle_url_verification(body: dict, cfg: FeishuConfig) -> tuple[int, dict] | None:
    """返回 (status_code, response_dict) 或 None。"""
    if body.get("type") == "url_verification":
        token = body.get("token", "")
        if cfg.verification_token and token != cfg.verification_token:
            return 403, {}
        return 200, {"challenge": body.get("challenge", "")}

    header = body.get("header") or {}
    if header.get("event_type") == "url_verification":
        event = body.get("event") or {}
        token = header.get("token") or event.get("token") or ""
        if cfg.verification_token and token and token != cfg.verification_token:
            return 403, {}
        return 200, {"challenge": event.get("challenge", "")}
    return None


def _extract_text_from_event(body: dict) -> tuple[str, str, str] | None:
    if body.get("_encrypt_only"):
        return None

    header = body.get("header") or {}
    event_type = header.get("event_type", "")

    if event_type == "im.message.receive_v1":
        event = body.get("event") or {}
        message = event.get("message") or {}
        msg_type = message.get("message_type", "")
        if msg_type not in ("text", "post"):
            log.info("忽略非文本消息 type=%s", msg_type)
            return None

        message_id = message.get("message_id", "")
        chat_id = message.get("chat_id", "")
        chat_type = message.get("chat_type", "?")
        content = _clean_command_text(_parse_message_content(message.get("content", "")))
        if message_id and content:
            log.info("消息 chat_type=%s msg_type=%s text=%r", chat_type, msg_type, content)
            return message_id, chat_id, content
        log.info(
            "消息解析为空 chat_type=%s message_id=%s raw=%s",
            chat_type,
            message_id,
            str(message.get("content", ""))[:200],
        )
        return None

    if body.get("type") == "event_callback":
        event = body.get("event") or {}
        if event.get("type") != "message" or event.get("msg_type") != "text":
            return None
        message_id = event.get("open_message_id") or event.get("message_id") or ""
        chat_id = event.get("open_chat_id") or event.get("chat_id") or ""
        content = _clean_command_text(_parse_message_content(event.get("text") or event.get("content") or ""))
        if message_id and content:
            return message_id, chat_id, content

    if event_type:
        log.info("未处理事件: %s", event_type)
    return None


def _process_message(cfg: FeishuConfig, message_id: str, chat_id: str, text: str) -> None:
    log.info("处理指令: %r message_id=%s chat_id=%s", text, message_id, chat_id)
    try:
        result = handle_command(text)
        file_key = ""
        file_path = result.file_path if result.file_path and os.path.isfile(result.file_path) else ""
        if file_path:
            try:
                file_key = upload_im_file(
                    cfg.app_id,
                    cfg.app_secret,
                    file_path,
                    file_type=result.file_type or "stream",
                    file_name=result.file_name,
                )
            except Exception as e:
                log.exception("上传文件失败")
                err = f"文件上传失败：{e}"
                if chat_id:
                    send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, err)
                else:
                    reply_text(cfg.app_id, cfg.app_secret, message_id, err)
                file_key = ""

        if result.text:
            for i, chunk in enumerate(split_reply(result.text)):
                try:
                    if i == 0:
                        reply_text(cfg.app_id, cfg.app_secret, message_id, chunk)
                    elif chat_id:
                        send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, chunk)
                    else:
                        reply_text(cfg.app_id, cfg.app_secret, message_id, chunk)
                except Exception as e:
                    log.warning("reply 失败，改 send_to_chat: %s", e)
                    if chat_id:
                        send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, chunk)
                    else:
                        raise
        elif not file_key:
            reply_text(cfg.app_id, cfg.app_secret, message_id, "（无回复内容）")

        if file_key:
            try:
                if chat_id:
                    send_file_to_chat(cfg.app_id, cfg.app_secret, chat_id, file_key)
                else:
                    reply_file(cfg.app_id, cfg.app_secret, message_id, file_key)
                log.info("已发送文件 %s", file_path)
            except Exception as e:
                log.exception("发送文件失败")
                err = f"文件发送失败：{e}"
                if chat_id:
                    send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, err)
                else:
                    reply_text(cfg.app_id, cfg.app_secret, message_id, err)
        log.info("已回复 %r", text)
    except Exception as e:
        log.exception("处理失败")
        err = f"处理失败：{e}"
        try:
            if chat_id:
                send_text_to_chat(cfg.app_id, cfg.app_secret, chat_id, err)
            else:
                reply_text(cfg.app_id, cfg.app_secret, message_id, err)
        except Exception:
            log.exception("错误提示发送失败")


class FeishuEventHandler(BaseHTTPRequestHandler):
    config: FeishuConfig

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, code: int, obj: dict) -> None:
        out = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/feishu/event", "/health"):
            self._send_json(200, {"ok": True, "service": "cyberadvisor-feishu-bot"})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/feishu/event", "/"):
            self.send_response(404)
            self.end_headers()
            return

        raw_bytes = _read_post_bytes(self)
        log.info("收到 POST %s bytes=%d", path, len(raw_bytes))
        _debug_log(
            f"POST headers={dict(self.headers)}",
            raw_bytes[:4000].decode("utf-8", errors="replace"),
        )

        body = _parse_body(raw_bytes, self.config)
        if body is None:
            log.error("无法解析请求体，详见 Wiki/数据/feishu_debug.log")
            self._send_json(400, {"error": "invalid body"})
            return

        verify = _handle_url_verification(body, self.config)
        if verify is not None:
            code, resp = verify
            if code == 200:
                log.info("URL 验证通过")
            self._send_json(code, resp)
            return

        header = body.get("header") or {}
        event_type = header.get("event_type") or body.get("type", "?")
        log.info("事件类型: %s", event_type)

        if self.config.verification_token:
            tok = header.get("token") or body.get("token") or ""
            if tok and tok != self.config.verification_token:
                log.error("token 不匹配")
                self.send_response(403)
                self.end_headers()
                return

        parsed = _extract_text_from_event(body)
        self._send_json(200, {})

        if parsed:
            message_id, chat_id, text = parsed
            threading.Thread(
                target=_process_message,
                args=(self.config, message_id, chat_id, text),
                daemon=True,
            ).start()


def make_handler(cfg: FeishuConfig) -> type[FeishuEventHandler]:
    return type("Handler", (FeishuEventHandler,), {"config": cfg})


def run_server(cfg: FeishuConfig, host: str = "0.0.0.0", port: int | None = None) -> None:
    if not cfg.bot_enabled:
        raise SystemExit(
            "Bot 未配置完整。需要 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_VERIFICATION_TOKEN"
        )
    port = port or cfg.bot_port
    handler = make_handler(cfg)
    server = HTTPServer((host, port), handler)
    log.info("飞书 Bot 监听 http://%s:%s/feishu/event", host, port)
    log.info("调试日志: Wiki/数据/feishu_debug.log")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("已停止")
        server.server_close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = FeishuConfig.load()
    run_server(cfg)


if __name__ == "__main__":
    main()
