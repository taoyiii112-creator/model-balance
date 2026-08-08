"""Windows 系统通知（Toast）封装：通过 PowerShell 调用系统通知，无第三方依赖。"""
from __future__ import annotations

import base64
import json
import subprocess

_TOAST_BODY = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $template.GetElementsByTagName('text')
$texts.Item(0).AppendChild($template.CreateTextNode($data.title)) | Out-Null
$texts.Item(1).AppendChild($template.CreateTextNode($data.body)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('模型余额').Show($toast)
"""


def _ps_single_quote(value: str) -> str:
    """转义为 PowerShell 单引号字符串（单引号翻倍）。"""
    return "'" + value.replace("'", "''") + "'"


def show_system_toast(title: str, body: str) -> bool:
    """展示一条 Windows 系统通知；失败返回 False（不抛异常，避免影响主流程）。"""
    try:
        payload = json.dumps(
            {"title": title, "body": body},
            ensure_ascii=False,
        )
        script = (
            f"$data = ConvertFrom-Json {_ps_single_quote(payload)};"
            + _TOAST_BODY
        )
        encoded = base64.b64encode(
            script.encode("utf-16-le")
        ).decode("ascii")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            timeout=15,
            creationflags=flags,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001 - 通知失败不影响主流程
        return False
