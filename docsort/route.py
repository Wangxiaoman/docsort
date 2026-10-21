"""路由分发：本地文件夹 / SMTP 邮件 / HTTP webhook（对接 ERP、OA）。"""
from __future__ import annotations

import json
import os
import shutil
import smtplib
import urllib.request
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from pathlib import Path
from typing import Optional


class RoutingError(RuntimeError):
    pass


def render(template: str, ctx: dict) -> str:
    """渲染路径/主题/正文模板。变量: {filename} {stem} {ext} {type} {confidence} {yyyy} {MM} {dd}。"""
    out = template
    for key, value in ctx.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _build_ctx(src: Path, doc_type: str, confidence: float, routing_cfg: dict) -> dict:
    now = datetime.now()
    return {
        "filename": src.name,
        "stem": src.stem,
        "ext": src.suffix,
        "type": doc_type,
        "confidence": f"{confidence:.2f}",
        "yyyy": now.strftime("%Y"),
        "MM": now.strftime("%m"),
        "dd": now.strftime("%d"),
        "date": now.strftime("%Y-%m-%d"),
        "output_dir": routing_cfg.get("output_dir", "./sorted"),
    }


def _resolve_conflict(target: Path, mode: str) -> Optional[Path]:
    """处理目标文件已存在的情况，返回最终落点（skip 模式返回 None）。"""
    if not target.exists() or mode == "overwrite":
        return target
    if mode == "skip":
        return None
    # rename: name (1).ext, name (2).ext ...
    n = 1
    while True:
        candidate = target.with_name(f"{target.stem} ({n}){target.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def route_folder(src: Path, tpl: dict, ctx: dict, routing_cfg: dict) -> str:
    raw = tpl.get("folder")
    if not raw:
        return ""
    rendered = render(raw, ctx)
    dest = Path(rendered).expanduser()
    if not dest.is_absolute():
        dest = Path.cwd() / dest
    # 模板已含 {filename}/{stem} 视为完整文件路径，否则视为目录
    if "{filename}" not in raw and "{stem}" not in raw:
        dest = dest / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    target = _resolve_conflict(dest, routing_cfg.get("on_conflict", "rename"))
    if target is None:
        return f"folder:skipped(已存在) {dest}"
    if routing_cfg.get("action", "move") == "copy":
        shutil.copy2(src, target)
        return f"folder:copied {target}"
    shutil.move(str(src), str(target))
    return f"folder:moved {target}"


def route_email(src: Path, tpl: dict, ctx: dict, mail_cfg: dict) -> str:
    if not tpl.get("email"):
        return ""
    to = render(tpl["email"].get("to", ""), ctx)
    if not to:
        return ""
    host = mail_cfg.get("host")
    if not host:
        raise RoutingError("邮件路由已配置但 routing.mail.host 为空")
    password = mail_cfg.get("password") or os.environ.get(mail_cfg.get("password_env", ""), "")
    if not password:
        raise RoutingError("邮件密码为空（配置 routing.mail.password 或环境变量）")

    subject = render(tpl["email"].get("subject", "文档识别: {filename}"), ctx)
    body = render(tpl["email"].get("body",
                  "识别类型: {type}\n置信度: {confidence}\n文件: {filename}"), ctx)
    sender_name = mail_cfg.get("from_name", "docsort")
    sender = mail_cfg.get("user", "")

    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header(sender_name, "utf-8")), sender))
    msg["To"] = to
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with open(src, "rb") as f:
        part = MIMEApplication(f.read())
    part.add_header("Content-Disposition", "attachment",
                    filename=Header(src.name, "utf-8"))
    msg.attach(part)

    port = int(mail_cfg.get("port", 465))
    if mail_cfg.get("use_ssl", True):
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    try:
        if mail_cfg.get("user"):
            server.login(mail_cfg["user"], password)
        server.sendmail(sender, [x.strip() for x in to.split(",") if x.strip()], msg.as_string())
    finally:
        server.quit()
    return f"email:sent -> {to}"


def route_webhook(src: Path, tpl: dict, ctx: dict, result: dict) -> str:
    hook = tpl.get("webhook") if isinstance(tpl.get("webhook"), dict) else None
    if not hook or not hook.get("url"):
        return ""
    payload = {
        "filename": src.name,
        "filepath": str(src.resolve()),
        "type": ctx["type"],
        "confidence": ctx["confidence"],
        "classified_at": datetime.now().isoformat(timespec="seconds"),
        **(result or {}),
    }
    req = urllib.request.Request(
        hook["url"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=hook.get("method", "POST").upper(),
    )
    try:
        with urllib.request.urlopen(req, timeout=hook.get("timeout", 10)) as resp:
            return f"webhook:{hook['url']} -> HTTP {resp.status}"
    except Exception as e:
        raise RoutingError(f"webhook 调用失败 {hook['url']}: {e}") from e


def dispatch(src: Path, doc_type: str, confidence: float, cfg: dict,
             result: Optional[dict] = None) -> list:
    """执行某分类模板下的全部路由。返回动作明细列表。"""
    tpl = cfg.get("templates", {}).get(doc_type, {})
    route_cfg = tpl.get("route", {}) or {}
    routing_cfg = cfg.get("routing", {})
    ctx = _build_ctx(src, doc_type, confidence, routing_cfg)
    actions: list = []
    errors: list = []

    if route_cfg.get("folder"):
        try:
            actions.append(route_folder(src, {"folder": route_cfg["folder"]}, ctx, routing_cfg))
        except Exception as e:
            errors.append(f"folder: {e}")

    if route_cfg.get("email"):
        try:
            actions.append(route_email(src, {"email": route_cfg["email"]}, ctx,
                                       routing_cfg.get("mail", {})))
        except Exception as e:
            errors.append(f"email: {e}")

    if route_cfg.get("webhook"):
        try:
            actions.append(route_webhook(src, {"webhook": route_cfg["webhook"]}, ctx, result))
        except Exception as e:
            errors.append(f"webhook: {e}")

    # 无 folder 路由时按 archive 配置归档，避免 watch 模式反复处理同一文件
    if not route_cfg.get("folder") and routing_cfg.get("archive"):
        archive_dir = Path(routing_cfg["archive"]).expanduser()
        if not archive_dir.is_absolute():
            archive_dir = Path.cwd() / archive_dir
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = _resolve_conflict(archive_dir / src.name, routing_cfg.get("on_conflict", "rename"))
        if target is not None:
            shutil.move(str(src), str(target))
            actions.append(f"archive:moved {target}")

    if errors:
        raise RoutingError("；".join(errors))
    return [a for a in actions if a]
