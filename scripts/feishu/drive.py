"""飞书云文档：按名称查找或按 URL 导出为 xlsx。"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from feishu.client import get_tenant_access_token

API = "https://open.feishu.cn/open-apis"

# 飞书云文档 type → 导出 API type
EXPORT_TYPES = {"sheet", "bitable", "doc", "docx"}
NATIVE_FILE_TYPE = "file"


def parse_cloud_url(url: str) -> tuple[str, str]:
    """从浏览器链接解析 (token, type)。"""
    url = url.strip()
    patterns = [
        (r"/sheets/([A-Za-z0-9_-]+)", "sheet"),
        (r"/sheet/([A-Za-z0-9_-]+)", "sheet"),
        (r"/base/([A-Za-z0-9_-]+)", "bitable"),
        (r"/bitable/([A-Za-z0-9_-]+)", "bitable"),
        (r"/docx/([A-Za-z0-9_-]+)", "docx"),
        (r"/docs/([A-Za-z0-9_-]+)", "docx"),
        (r"/file/([A-Za-z0-9_-]+)", "file"),
        (r"/wiki/([A-Za-z0-9_-]+)", "wiki"),
    ]
    for pat, doc_type in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1), doc_type
    raise ValueError(f"无法从链接解析文档 token：{url}")


def _api_json(
    method: str,
    path: str,
    access_token: str,
    *,
    query: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    url = API + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = None
    headers = {"Authorization": f"Bearer {access_token}"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"飞书 API HTTP {e.code} {path}: {detail}") from e
    if not raw:
        return {}
    out = json.loads(raw.decode("utf-8"))
    if out.get("code") != 0:
        raise RuntimeError(f"飞书 API 失败 {path}: {out}")
    return out


def _download_bytes(path: str, access_token: str, timeout: int = 120) -> bytes:
    url = API + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"飞书下载 HTTP {e.code}: {detail}") from e


def get_root_folder_token(access_token: str) -> str:
    body = _api_json("GET", "/drive/explorer/v2/root_folder/meta", access_token)
    token = body.get("data", {}).get("token")
    if not token:
        raise RuntimeError(f"获取根目录 token 失败: {body}")
    return token


def find_file_in_folder(
    access_token: str,
    folder_token: str,
    name: str,
    *,
    recursive: bool = True,
    _depth: int = 0,
) -> tuple[str, str] | None:
    """按文件名查找，返回 (token, type)。匹配「持仓」或「持仓.xlsx」。"""
    targets = {name.strip(), f"{name.strip()}.xlsx", name.strip().removesuffix(".xlsx")}
    page_token = ""
    while True:
        query: dict[str, str] = {"folder_token": folder_token, "page_size": "200"}
        if page_token:
            query["page_token"] = page_token
        body = _api_json("GET", "/drive/v1/files", access_token, query=query)
        data = body.get("data", {}) or {}
        for item in data.get("files", []) or []:
            fname = str(item.get("name", "")).strip()
            ftoken = str(item.get("token", "")).strip()
            ftype = str(item.get("type", "")).strip()
            if not ftoken:
                continue
            if fname in targets or fname.removesuffix(".xlsx") in targets:
                return ftoken, ftype
            if recursive and ftype == "folder" and _depth < 4:
                found = find_file_in_folder(
                    access_token, ftoken, name, recursive=True, _depth=_depth + 1
                )
                if found:
                    return found
        page_token = data.get("next_page_token") or ""
        if not page_token:
            break
    return None


def _resolve_wiki_sheet(access_token: str, wiki_token: str) -> tuple[str, str]:
    """知识库节点 → 实际文档 token（常见为 sheet）。"""
    body = _api_json(
        "GET",
        f"/wiki/v2/spaces/get_node",
        access_token,
        query={"token": wiki_token},
    )
    node = body.get("data", {}).get("node", {}) or {}
    obj_token = node.get("obj_token") or node.get("object_token")
    obj_type = node.get("obj_type") or node.get("object_type") or "sheet"
    if not obj_token:
        raise RuntimeError(f"无法解析知识库节点文档: {body}")
    return str(obj_token), str(obj_type)


def _export_online_doc(access_token: str, doc_token: str, doc_type: str) -> bytes:
    if doc_type not in EXPORT_TYPES:
        raise ValueError(f"类型 {doc_type} 不支持导出 xlsx，请使用 sheet/bitable 链接")
    create = _api_json(
        "POST",
        "/drive/v1/export_tasks",
        access_token,
        body={"file_extension": "xlsx", "token": doc_token, "type": doc_type},
    )
    ticket = create.get("data", {}).get("ticket")
    if not ticket:
        raise RuntimeError(f"创建导出任务失败: {create}")

    file_token = ""
    for _ in range(40):
        time.sleep(2)
        status = _api_json(
            "GET",
            f"/drive/v1/export_tasks/{ticket}",
            access_token,
            query={"token": doc_token},
        )
        result = status.get("data", {}).get("result") or {}
        file_token = result.get("file_token") or ""
        job_status = result.get("job_status")
        if file_token:
            break
        if job_status in (2, 3):
            raise RuntimeError(f"导出任务失败: {status}")
    if not file_token:
        raise RuntimeError("导出超时（80s），请稍后重试")

    return _download_bytes(f"/drive/v1/export_tasks/file/{file_token}/download", access_token)


def _download_native_file(access_token: str, file_token: str) -> bytes:
    return _download_bytes(f"/drive/v1/files/{file_token}/download", access_token)


def download_portfolio_xlsx(
    app_id: str,
    app_secret: str,
    dest_path: str,
    *,
    cloud_url: str = "",
    doc_token: str = "",
    doc_type: str = "",
    file_name: str = "",
    folder_token: str = "",
) -> tuple[str, str]:
    """
    下载/导出飞书云文档为 xlsx，写入 dest_path。
    返回 (source_token, source_type) 供日志使用。
    """
    access_token = get_tenant_access_token(app_id, app_secret)

    token, dtype = "", ""
    if cloud_url:
        token, dtype = parse_cloud_url(cloud_url)
    elif doc_token and doc_type:
        token, dtype = doc_token, doc_type
    elif file_name:
        folder = folder_token or get_root_folder_token(access_token)
        found = find_file_in_folder(access_token, folder, file_name)
        if not found:
            raise FileNotFoundError(
                f"在云盘未找到名为「{file_name}」的文件（folder={folder}）"
            )
        token, dtype = found
    else:
        raise ValueError("未指定飞书持仓来源")

    if dtype == "wiki":
        token, dtype = _resolve_wiki_sheet(access_token, token)

    if dtype == NATIVE_FILE_TYPE:
        data = _download_native_file(access_token, token)
    elif dtype in EXPORT_TYPES:
        data = _export_online_doc(access_token, token, dtype)
    else:
        raise ValueError(f"不支持的云文档类型: {dtype}")

    if not data.startswith(b"PK"):
        raise RuntimeError("下载内容不是有效 xlsx（缺少 ZIP 文件头 PK）")

    with open(dest_path, "wb") as f:
        f.write(data)
    return token, dtype
