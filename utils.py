# Refactor: 泛用性改造
import re
from datetime import datetime


def get_timestamp() -> str:
    now = datetime.now()
    return f"[{now.year}.{now.month}.{now.day}/{now.hour:02d}:{now.minute:02d}]"


def sanitize_reply(text: str, strip_chars: str = r'[<>{}|^`\\*/\x00-\x1f\x7f-\x9f  ￰-￿​-‏‪-‮⁠-⁯]') -> str:
    """清理 AI 回复，移除可能导致命令注入或踢出的特殊字符。
    覆盖范围：Minecraft 控制字符、零宽字符、双向文本控制符、Unicode 格式字符。
    strip_chars: 正则字符类，<>{}|^`\\*/ 等结构性危险字符始终清理。
    """
    text = text.replace('', ' ')
    cleaned = re.sub(strip_chars, '', text)
    cleaned = cleaned.replace('\n', ' ').replace('\r', ' ')
    return cleaned.strip()


# 向后兼容别名
clean_for_minecraft = sanitize_reply


def truncate_to_bytes(text: str, max_bytes: int) -> str:
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(text[:mid].encode('utf-8')) <= max_bytes - 3:
            lo = mid
        else:
            hi = mid - 1
    if lo == 0:
        return "..."
    return text[:lo] + "..."


def build_command(text: str, max_bytes: int, mode: str = "me") -> str:
    """构建发送命令，mode 可选 "me" / "say" / "raw" / "json"，超出字节数自动截断。"""
    if mode == "json":
        import json as _json
        payload = _json.dumps(
            {"type": "chat", "body": {"content": text}},
            ensure_ascii=False,
        )
        if len(payload.encode("utf-8")) <= max_bytes:
            return payload
        truncated = truncate_to_bytes(text, max_bytes - 200)
        return _json.dumps(
            {"type": "chat", "body": {"content": truncated}},
            ensure_ascii=False,
        )

    if mode == "raw":
        if len(text.encode("utf-8")) <= max_bytes:
            return text
        return truncate_to_bytes(text, max_bytes)

    prefix = f"/{mode} "
    command = f"{prefix}{text}"
    if len(command.encode('utf-8')) <= max_bytes:
        return command
    available = max_bytes - len(prefix.encode('utf-8'))
    if available <= 3:
        return f"{prefix}..."
    truncated = truncate_to_bytes(text, available)
    return f"{prefix}{truncated}"


def make_safe_command(prefix: str, body: str, max_bytes: int, send_mode: str = "me") -> str:
    """构建 AI 回复命令，必要时截断 body。"""
    text = f"{prefix}{body}"
    return build_command(text, max_bytes, mode=send_mode)


def make_safe_say(text: str, max_bytes: int) -> str:
    return build_command(text, max_bytes, mode="say")


def make_safe_me(text: str, max_bytes: int) -> str:
    return build_command(text, max_bytes, mode="me")


def make_send_text(text: str, max_bytes: int, send_mode: str = "me") -> str:
    """按指定 send_mode 构建发送内容，用于简单文本（无 prefix）。"""
    return build_command(text, max_bytes, mode=send_mode)


def timestamp_to_seconds(ts_str: str) -> float:
    try:
        dt_str = ts_str.strip('[]').replace('/', ' ').replace('.', '-')
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
        return dt.timestamp()
    except Exception:
        return 0
