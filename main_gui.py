# Fixed: BUG-6, BUG-7, P0-P3 design issues
"""
MC AI Bot — Web GUI
启动后在浏览器中管理实例、配置参数、监控运行状态。
"""
import asyncio
import itertools
import json
import os
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

from collections import deque

import aiohttp
from aiohttp import web

from config import get_data_root
from instance import BotInstance, INSTANCES_DIR_NAME
from main import MinecraftBot, is_instance_running, _clear_pid

PORT = 18750


# ============================================================
# 轻量信号 — 模仿 Qt signals，与 MinecraftBot 已有接口兼容
# ============================================================
class Signal:
    def __init__(self):
        self._callbacks: list = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for cb in self._callbacks:
            try:
                cb(*args)
            except Exception as e:
                import traceback
                # 【修复】遇到异常打印堆栈，而不是悄无声息地死掉
                print(f"[CRITICAL] Signal 回调触发异常: {e}")
                traceback.print_exc()


class BotSignals:
    def __init__(self):
        self.log_line = Signal()
        self.model_changed = Signal()
        self.ws_connected = Signal()
        self.status_message = Signal()
        self.stopped = Signal()


# ============================================================
# Bot 管理器
# ============================================================
class BotManager:
    """管理各实例的运行中 bot。"""

    def __init__(self):
        self._bots: dict[str, dict] = {}  # name → {bot, task, signals, subscribers, buffer}

    @staticmethod
    def _runtime_state_path(instance) -> Path:
        return instance.folder / "runtime_state.json"

    @classmethod
    def _load_runtime_state(cls, instance) -> dict:
        path = cls._runtime_state_path(instance)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    @classmethod
    def _save_runtime_state(cls, instance, state: dict) -> None:
        path = cls._runtime_state_path(instance)
        # merge with existing
        existing = cls._load_runtime_state(instance)
        existing.update(state)
        path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")

    def is_running(self, name: str) -> bool:
        if name in self._bots:
            return True
        return is_instance_running(name)

    def subscribe(self, name: str) -> asyncio.Queue | None:
        """为一个新的 WebSocket 连接创建独立队列并注册为订阅者。
        # [FIX-P0-11] 每个连接独立队列，避免多个连接抢同一份消息导致丢失
        """
        entry = self._bots.get(name)
        if not entry:
            return None
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        entry["subscribers"].append(q)
        print(f"[DEBUG] 控制台订阅者 +1 → {name}: 当前 {len(entry['subscribers'])} 个连接")
        return q

    def unsubscribe(self, name: str, q: asyncio.Queue) -> None:
        """# [FIX-P0-11] 连接断开后移除订阅，防止 subscribers 列表无限增长"""
        entry = self._bots.get(name)
        if entry and q in entry["subscribers"]:
            entry["subscribers"].remove(q)
            print(f"[DEBUG] 控制台订阅者 -1 → {name}: 当前 {len(entry['subscribers'])} 个连接")

    def get_recent_messages(self, name: str) -> list[dict]:
        entry = self._bots.get(name)
        return list(entry["buffer"]) if entry else []

    async def start(self, name: str) -> str:
        if name in self._bots:
            return "已在运行"

        instance = BotInstance.load(name)
        if not instance:
            return f"实例 '{name}' 加载失败"

        subscribers: list[asyncio.Queue] = []  # [FIX-P0-11] 替代原来的单一共享队列
        buffer: deque[dict] = deque(maxlen=200)  # 保留最近 200 条供新 WebSocket 客户端回放

        _seq_counter = itertools.count(1)

        def on_message(line: str, msg_type: str = "info"):
            ts = ""
            entry_data = {"ts": ts, "text": line, "type": msg_type, "seq": next(_seq_counter)}
            buffer.append(entry_data)
            # [FIX-P0-11] 广播给所有当前订阅者，而不是塞进一个大家抢的共享队列
            for q in list(subscribers):
                try:
                    q.put_nowait(entry_data)
                except asyncio.QueueFull:
                    # 【修复】队列满时发出明确警告，而不是静默丢弃
                    print("[WARN] GUI 控制台消息队列已满，Web 前端可能丢日志")
                except Exception as e:
                    # 【修复】捕获其它所有底层的序列化或同步异常，并打印堆栈，避免静默死亡
                    import traceback
                    print(f"[CRITICAL ERROR] 消息入队失败，原因: {e}")
                    traceback.print_exc()

        signals = BotSignals()
        signals.log_line.connect(on_message)
        signals.status_message.connect(lambda msg: on_message(msg, "warn"))

        def on_stopped():
            on_message("机器人已停止", "warn")

        signals.stopped.connect(on_stopped)

        saved = self._load_runtime_state(instance)
        runtime = {
            "enable_reply": saved.get("enable_reply", False),  # [FIX-P0-9] 默认关闭回复
            "enable_auto_comment": saved.get("enable_auto_comment", False),  # [FIX-P0-9] 默认关闭氛围评论
            "enable_logging": saved.get("enable_logging", True),
            "trigger_prefix": saved.get("trigger_prefix", instance.trigger_prefix),
            "send_mode": saved.get("send_mode", instance.send_mode),
        }
        bot = MinecraftBot(instance, signals=signals, runtime=runtime)

        async def _runner():
            try:
                await bot.run()
            except Exception:
                on_message(traceback.format_exc(), "error")
            finally:
                self._bots.pop(name, None)

        task = asyncio.create_task(_runner())
        self._bots[name] = {
            "bot": bot, "task": task, "signals": signals,
            "subscribers": subscribers, "buffer": buffer,
        }
        return "ok"

    async def stop(self, name: str) -> str:
        entry = self._bots.get(name)
        if not entry:
            return "未在运行"
        try:
            await entry["bot"].shutdown()
        except Exception:
            pass
        # 【修复】取消并等待后台任务退出，确保 WebSocket 连接被彻底关闭
        task = entry.get("task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._bots.pop(name, None)
        return "ok"

    async def stop_all(self):
        for name in list(self._bots):
            await self.stop(name)


bot_manager = BotManager()


# ============================================================
# API 路由
# ============================================================
routes = web.RouteTableDef()


_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}

def _json(data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return web.Response(body=body, status=status,
                        headers={"Content-Type": "application/json; charset=utf-8",
                                 **_NO_CACHE})


@routes.get("/api/instances")
async def api_list(_req):
    names = BotInstance.list_instances()
    # 读取置顶列表
    pinned_file = get_data_root() / INSTANCES_DIR_NAME / "_pinned.json"
    pinned = []
    if pinned_file.exists():
        try:
            pinned = json.loads(pinned_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pinned = []
    # 置顶的排前面
    ordered = [n for n in pinned if n in names] + [n for n in names if n not in pinned]
    result = []
    for n in ordered:
        inst = BotInstance.load(n)
        running = bot_manager.is_running(n)
        result.append({
            "name": n,
            "bot_name": inst.bot_name,
            "model": inst.model_flash,
            "ws_url": inst.ws_url,
            "running": running,
            "local": n in bot_manager._bots,
            "pinned": n in pinned,
        })
    return _json(result)


@routes.post("/api/instances")
async def api_create(req):
    data = await req.json()
    name = data.get("name", "").strip()
    template = data.get("template", "").strip() or None
    if not name:
        return _json({"error": "名称不能为空"}, 400)
    if name in BotInstance.list_instances():
        return _json({"error": "实例已存在"}, 409)
    inst = BotInstance.create(name, template=BotInstance.load(template) if template else None)
    return _json({"name": name, "bot_name": inst.bot_name})


@routes.post("/api/instances/import")
async def api_import(req):
    data = await req.json()
    name = data.get("name", "").strip()
    # [FIX-P0-13] 和 api_update_config（PUT /api/instances/{name}）保持一致：
    # 兼容前端把导出字段直接摊平在请求体顶层、而不是嵌套在 "config" 键下的情况。
    # 旧代码 data.get("config", {}) 一旦没嵌套就永远拿到空字典，导致导入形同虚设。
    config = data.get("config", data)
    if not isinstance(config, dict):
        config = {}
    if not name:
        return _json({"error": "名称不能为空"}, 400)
    if name in BotInstance.list_instances():
        return _json({"error": "实例已存在"}, 409)

    # 【诊断】打印收到的请求结构
    print(f"[DEBUG] 导入请求: name={name}, data顶层keys={list(data.keys())}, "
          f"config类型={type(config).__name__}, config_keys={list(config.keys())[:10]}")

    # 【安全】无论导入文件里是否包含 API Key，一律忽略，绝不落盘。
    # 下面做了两层过滤：先从 dict 里彻底删掉，循环里再跳过一次，
    # 任何一层被后续修改误删都还有另一层兜底，谁都不许合并简化成一层。
    config = dict(config)
    config.pop("deepseek_api_key", None)
    config.pop("_note", None)
    config.pop("name", None)  # 实例名只认表单里填的，不认导入文件里的

    inst = BotInstance.create(name)  # 先建空白实例，API Key 天然是空的

    print(f"[DEBUG] 处理后config_keys={list(config.keys())}")

    # [FIX-P0-13] 诊断日志：若 config 为空，提示用户检查请求体格式
    if not config:
        print(f"[WARN] 导入实例 '{name}' 时未解析到任何配置字段，将使用默认配置")

    changed_prompts = False
    changed_commands = False
    for k, v in config.items():
        if k == "deepseek_api_key":
            continue
        if hasattr(inst, k):
            setattr(inst, k, v)
            if k in ("system_prompt", "auto_comment_prompt"):
                changed_prompts = True
            elif k == "custom_commands":
                changed_commands = True

    inst.save_env()
    if changed_prompts:
        inst.save_prompts()
    if changed_commands:
        inst.save_commands()

    return _json({"name": name, "bot_name": inst.bot_name})


@routes.delete("/api/instances/{name}")
async def api_delete(req):
    name = req.match_info["name"]
    if name not in BotInstance.list_instances():
        return _json({"error": "实例不存在"}, 404)
    if bot_manager.is_running(name):
        return _json({"error": "请先停止机器人"}, 409)
    try:
        BotInstance.load(name).delete()
    except Exception:
        # 加载失败时直接删文件夹
        import shutil
        shutil.rmtree(BotInstance._get_folder(name))
    return _json({"ok": True})


@routes.post("/api/instances/{name}/duplicate")
async def api_duplicate(req):
    name = req.match_info["name"]
    data = await req.json()
    new_name = data.get("new_name", "").strip()
    if not new_name:
        return _json({"error": "新名称不能为空"}, 400)
    if new_name in BotInstance.list_instances():
        return _json({"error": "目标名称已存在"}, 409)
    BotInstance.load(name).duplicate(new_name)
    return _json({"name": new_name})


@routes.post("/api/instances/{name}/pin")
async def api_pin(req):
    name = req.match_info["name"]
    if name not in BotInstance.list_instances():
        return _json({"error": "实例不存在"}, 404)
    pinned_file = get_data_root() / INSTANCES_DIR_NAME / "_pinned.json"
    pinned = []
    if pinned_file.exists():
        try:
            pinned = json.loads(pinned_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pinned = []
    if name in pinned:
        pinned.remove(name)
        action = "unpinned"
    else:
        pinned.insert(0, name)
        action = "pinned"
    pinned_file.write_text(json.dumps(pinned, ensure_ascii=False), encoding="utf-8")
    return _json({"ok": True, "action": action})


@routes.get("/api/instances/{name}/export")
async def api_export(req):
    name = req.match_info["name"]
    if name not in BotInstance.list_instances():
        return _json({"error": "实例不存在"}, 404)
    inst = BotInstance.load(name)
    cfg = {
        "name": inst.name,
        "deepseek_api_key": inst.deepseek_api_key,
        "deepseek_api_url": inst.deepseek_api_url,
        "model_pro": inst.model_pro,
        "model_flash": inst.model_flash,
        "ws_url": inst.ws_url,
        "bot_name": inst.bot_name,
        "admin_username": inst.admin_username,
        "sender_patterns": inst.sender_patterns,
        "trigger_prefix": inst.trigger_prefix,
        "send_mode": inst.send_mode,
        "cooldown_seconds": inst.cooldown_seconds,
        "reply_prefix": inst.reply_prefix,
        "comment_prefix": inst.comment_prefix,
        "system_msg_prefix": inst.system_msg_prefix,  # [FIX-P0-14] 导出遗漏字段
        "skip_msg_prefix": inst.skip_msg_prefix,  # [FIX-P0-14] 导出遗漏字段
        "log_dir": inst.log_dir,
        "max_history": inst.max_history,
        "global_context_size": inst.global_context_size,
        "max_command_bytes": inst.max_command_bytes,
        "auto_comment_interval": inst.auto_comment_interval,
        "heartbeat_check_interval": inst.heartbeat_check_interval,
        "heartbeat_timeout": inst.heartbeat_timeout,
        "api_timeout": inst.api_timeout,
        "temperature": inst.temperature,
        "max_tokens": inst.max_tokens,
        "retry_count": inst.retry_count,
        "retry_delay": inst.retry_delay,
        "reconnect_delay": inst.reconnect_delay,
        "reconnect_delay_long": inst.reconnect_delay_long,
        "system_prompt": inst.system_prompt,
        "auto_comment_prompt": inst.auto_comment_prompt,
        "custom_commands": inst.custom_commands,
    }
    cfg["deepseek_api_key"] = ""
    cfg["_note"] = "API Key 已从导出中移除，请手动填入"
    body = json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
    return web.Response(
        body=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{name}_config.json"',
        },
    )


@routes.post("/api/instances/{name}/rename")
async def api_rename(req):
    name = req.match_info["name"]
    data = await req.json()
    new_name = data.get("new_name", "").strip()
    if not new_name:
        return _json({"error": "新名称不能为空"}, 400)
    if new_name == name:
        return _json({"ok": True, "name": name})
    if new_name in BotInstance.list_instances():
        return _json({"error": "目标名称已存在"}, 409)
    if bot_manager.is_running(name):
        return _json({"error": "请先停止机器人再重命名"}, 409)
    BotInstance.load(name).rename(new_name)
    return _json({"ok": True, "name": new_name})


@routes.get("/api/instances/{name}")
async def api_get_config(req):
    name = req.match_info["name"]
    if name not in BotInstance.list_instances():
        return _json({"error": "实例不存在"}, 404)
    try:
        inst = BotInstance.load(name)
    except Exception as e:
        return _json({"error": f"加载失败: {e}", "broken": True, "name": name}, 500)
    return _json({
        "name": name,
        "running": bot_manager.is_running(name),
        "local": name in bot_manager._bots,
        "runtime_state": bot_manager._load_runtime_state(inst),
        "config": {
            "deepseek_api_key": inst.deepseek_api_key,
            "deepseek_api_url": inst.deepseek_api_url,
            "model_pro": inst.model_pro,
            "model_flash": inst.model_flash,
            "ws_url": inst.ws_url,
            "bot_name": inst.bot_name,
            "admin_username": inst.admin_username,
            "sender_patterns": inst.sender_patterns,
            "trigger_prefix": inst.trigger_prefix,
            "send_mode": inst.send_mode,
            "cooldown_seconds": inst.cooldown_seconds,
            "reply_prefix": inst.reply_prefix,
            "comment_prefix": inst.comment_prefix,
            "system_msg_prefix": inst.system_msg_prefix,  # [FIX-P0-14] 读取遗漏字段
            "skip_msg_prefix": inst.skip_msg_prefix,  # [FIX-P0-14] 读取遗漏字段
            "log_dir": inst.log_dir,
            "max_history": inst.max_history,
            "global_context_size": inst.global_context_size,
            "max_command_bytes": inst.max_command_bytes,
            "auto_comment_interval": inst.auto_comment_interval,
            "heartbeat_check_interval": inst.heartbeat_check_interval,
            "heartbeat_timeout": inst.heartbeat_timeout,
            "api_timeout": inst.api_timeout,
            "temperature": inst.temperature,
            "max_tokens": inst.max_tokens,
            "retry_count": inst.retry_count,
            "retry_delay": inst.retry_delay,
            "reconnect_delay": inst.reconnect_delay,
            "reconnect_delay_long": inst.reconnect_delay_long,
            "system_prompt": inst.system_prompt,
            "auto_comment_prompt": inst.auto_comment_prompt,
            "custom_commands": inst.custom_commands,
        },
    })


@routes.put("/api/instances/{name}")
async def api_update_config(req):
    name = req.match_info["name"]
    if name not in BotInstance.list_instances():
        return _json({"error": "实例不存在"}, 404)
    if bot_manager.is_running(name):
        return _json({"error": "请先停止机器人再修改配置"}, 409)
    data = await req.json()
    inst = BotInstance.load(name)
    config = data.get("config", data)
    changed_prompts = False
    changed_commands = False
    for k, v in config.items():
        if hasattr(inst, k):
            setattr(inst, k, v)
            if k in ("system_prompt", "auto_comment_prompt"):
                changed_prompts = True
            elif k == "custom_commands":
                changed_commands = True
    inst.save_env()
    if changed_prompts:
        inst.save_prompts()
    if changed_commands:
        inst.save_commands()
    return _json({"ok": True})


@routes.post("/api/instances/{name}/start")
async def api_start(req):
    name = req.match_info["name"]
    result = await bot_manager.start(name)
    if result == "ok":
        return _json({"ok": True})
    return _json({"error": result}, 400)


@routes.post("/api/instances/{name}/stop")
async def api_stop(req):
    name = req.match_info["name"]
    result = await bot_manager.stop(name)
    if result == "ok":
        return _json({"ok": True})
    return _json({"error": result}, 400)


@routes.post("/api/instances/{name}/runtime")
async def api_runtime(req):
    """热更新运行时设置。机器人运行中：立即生效并持久化。
    未运行：只持久化到 runtime_state.json，下次启动时自动读取生效。"""
    name = req.match_info["name"]
    data = await req.json()
    entry = bot_manager._bots.get(name)
    if entry:
        entry["bot"].update_runtime(**data)
        bot_manager._save_runtime_state(entry["bot"].instance, data)
        return _json({"ok": True})

    inst = BotInstance.load(name)
    if not inst:
        return _json({"error": "实例不存在"}, 404)
    bot_manager._save_runtime_state(inst, data)
    return _json({"ok": True})


@routes.post("/api/instances/{name}/send")
async def api_send(req):
    name = req.match_info["name"]
    entry = bot_manager._bots.get(name)
    if not entry:
        return _json({"error": "机器人未运行"}, 400)
    data = await req.json()
    text = data.get("text", "").strip()
    if not text:
        return _json({"error": "内容为空"}, 400)

    # 【修复】拦截 /perception、/reply、/replay 命令，不当作普通消息发送
    if text == "/perception":
        entry["bot"].trigger_comment()
        return _json({"ok": True, "action": "trigger_comment"})
    if text in ("/reply", "/replay"):
        entry["bot"].trigger_reply_recent()
        return _json({"ok": True, "action": "trigger_reply_recent"})

    if text in ("/switch pro", "/pro"):
        model = entry["bot"].switch_model("pro")
        return _json({"ok": True, "action": "switch_model", "model": model})
    if text in ("/switch flash", "/flash"):
        model = entry["bot"].switch_model("flash")
        return _json({"ok": True, "action": "switch_model", "model": model})

    # [FIX-P0-5] raw 模式下以 "/" 开头的文本会被解释为 MC 指令，绕过权限检查直接执行
    if entry["bot"].send_mode == "raw" and text.startswith("/"):
        return _json({"error": "raw 模式下不允许发送指令"}, 403)

    entry["bot"].queue_send(text, use_prefix=data.get("use_prefix", False))
    return _json({"ok": True})


@routes.post("/api/instances/{name}/clear-pid")
async def api_clear_pid(req):
    name = req.match_info["name"]
    from main import _clear_pid
    inst = BotInstance.load(name)
    _clear_pid(inst.folder)
    return _json({"ok": True})


@routes.post("/api/instances/{name}/trigger-comment")
async def api_trigger_comment(req):
    name = req.match_info["name"]
    entry = bot_manager._bots.get(name)
    if not entry:
        return _json({"error": "机器人未运行"}, 400)
    entry["bot"].trigger_comment()
    return _json({"ok": True})


@routes.post("/api/instances/{name}/reply-recent")
async def api_reply_recent(req):
    name = req.match_info["name"]
    entry = bot_manager._bots.get(name)
    if not entry:
        return _json({"error": "机器人未运行"}, 400)
    entry["bot"].trigger_reply_recent()
    return _json({"ok": True})


@routes.post("/api/instances/{name}/sync-logs")
async def api_sync_logs(req):
    """从总 TXT 同步生成 HTML 和按天文件。"""
    from logger import ChatLogger

    name = req.match_info["name"]
    inst = BotInstance.load(name)
    log_dir = str(inst.folder / inst.log_dir)
    logger = ChatLogger(log_dir)
    try:
        result = logger.sync()
        return _json({"ok": True, **result})
    except Exception as e:
        return _json({"error": str(e)}, 500)
    finally:
        logger.close()


@routes.post("/api/instances/{name}/open-log-folder")
async def api_open_log_folder(req):
    name = req.match_info["name"]
    inst = BotInstance.load(name)
    folder = inst.folder / inst.log_dir
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(folder))
    except Exception as e:
        return _json({"error": str(e)}, 500)
    return _json({"ok": True, "path": str(folder)})


@routes.get("/api/instances/{name}/console")
async def api_console(req):
    name = req.match_info["name"]
    recent = bot_manager.get_recent_messages(name)
    return _json(recent)


# ============================================================
# WebSocket — 实时控制台
# ============================================================
@routes.get("/ws/console/{name}")
async def ws_console(req):
    name = req.match_info["name"]
    ws = web.WebSocketResponse()
    await ws.prepare(req)

    queue = bot_manager.subscribe(name)  # [FIX-P0-11] 每个连接一份独立队列
    if not queue:
        await ws.send_json({"text": "机器人未运行", "type": "warn"})
        await ws.close()
        return ws

    # [FIX-P0-11] 确保无论从哪个分支退出都清理订阅
    try:
        # 先发送缓冲的历史消息（供页面刷新后回放），并记录回放到的最大 seq
        last_seq = 0
        try:
            for entry in bot_manager.get_recent_messages(name):
                await ws.send_json(entry)
                last_seq = max(last_seq, entry.get("seq", 0))
        except Exception as e:
            print(f"[WARN] 发送历史缓冲消息失败: {e}, 终止当前连接")
            await ws.close()
            return ws

        # 【修复】不再无脑清空 queue —— 旧逻辑会把"buffer 快照之后、这行代码执行之前"
        # 刚好到达的新消息也当成重复项一并冲掉，导致这段时间窗口内的消息永久丢失
        # （表现为：游戏里有，网页控制台和日志里完全没有）。
        # 现在改成按 seq 精确判断：seq <= last_seq 的才是真正已经回放过的重复项，
        # 丢弃它们；seq 更大的说明是新消息，必须补发，不能丢。
        pending = []
        try:
            while True:
                entry = queue.get_nowait()
                if entry.get("seq", 0) > last_seq:
                    pending.append(entry)
        except asyncio.QueueEmpty:
            pass
        for entry in pending:
            await ws.send_json(entry)

        while not ws.closed:
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=2.0)
                try:
                    await ws.send_json(entry)
                except Exception as e:
                    print(f"[ERROR] 发送消息到 Web 前端失败: {e}")
                    return ws
            except asyncio.TimeoutError:
                if not bot_manager.is_running(name):
                    await ws.send_json({"text": "机器人已停止", "type": "warn"})
                    break
            except Exception as e:
                print(f"[ERROR] 控制台消费者循环异常: {e}")
                return ws
    finally:
        bot_manager.unsubscribe(name, queue)  # [FIX-P0-11] 无论从哪个分支退出都要清理订阅
        await ws.close()
    return ws


# ============================================================
# 系统工具
# ============================================================

@routes.post("/api/browse-folder")
async def api_browse_folder(req):
    """弹出系统原生文件夹选择框，返回选中路径。"""
    import subprocess, sys, traceback
    try:
        script = Path(__file__).resolve().parent / "scripts" / "pick_folder.py"
        if not script.exists():
            return _json({"error": f"选择器脚本不存在: {script}"}, 500)

        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            print(f"\n[ERROR] pick_folder.py 子进程错误:\n{err}")
            return _json({"error": f"选择器子进程退出码 {proc.returncode}"}, 500)

        folder = stdout.decode("utf-8", errors="replace").strip()
        return _json({"path": folder})
    except asyncio.TimeoutError:
        return _json({"error": "文件夹选择超时"}, 500)
    except Exception:
        tb = traceback.format_exc()
        print(f"\n[ERROR] /api/browse-folder 异常:\n{tb}")
        return _json({"error": tb}, 500)


@routes.post("/api/shutdown")
async def api_shutdown(req):
    """停掉所有 bot 并退出整个服务器进程。"""
    print("\n[系统] API 请求关闭服务器…")
    await bot_manager.stop_all()
    loop = asyncio.get_event_loop()
    loop.call_later(0.5, loop.stop)
    return _json({"ok": True, "message": "正在关闭服务器…"})


# ============================================================
# 使用说明
# ============================================================

@routes.get("/api/usage-guide")
async def api_usage_guide(_req):
    """返回使用说明 Markdown 文档。"""
    from config import get_resource_root
    doc_path = get_resource_root() / "docs" / "USAGE.md"
    if not doc_path.exists():
        return _json({"error": "使用说明文件不存在"}, 404)
    content = doc_path.read_text(encoding="utf-8")
    return web.Response(
        body=content.encode("utf-8"),
        headers={"Content-Type": "text/markdown; charset=utf-8", **_NO_CACHE},
    )


# ============================================================
# 静态文件服务 — SPA 前端 (正确配置)
# ============================================================

FRONTEND_DIST = Path(sys._MEIPASS if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent) / "frontend" / "dist"


def setup_static_files(app: web.Application):
    """用 aiohttp 原生方式挂载静态文件与 SPA 回退。"""
    # 方法 1：add_static 自动处理 JS/CSS 的 MIME 类型、缓存、Range 等
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets", assets_dir)

    # 方法 2：根目录下的静态文件（favicon）
    favicon_path = FRONTEND_DIST / "favicon.svg"
    if favicon_path.exists():
        async def _favicon(_req):
            return web.FileResponse(favicon_path)
        app.router.add_get("/favicon.svg", _favicon)

    favicon_png_path = FRONTEND_DIST / "favicon.png"
    if favicon_png_path.exists():
        async def _favicon_png(_req):
            return web.FileResponse(favicon_png_path)
        app.router.add_get("/favicon.png", _favicon_png)
        app.router.add_get("/favicon.ico", _favicon_png)  # 兼容部分浏览器

    apple_touch_path = FRONTEND_DIST / "apple-touch-icon.png"
    if apple_touch_path.exists():
        async def _apple_touch(_req):
            return web.FileResponse(apple_touch_path)
        app.router.add_get("/apple-touch-icon.png", _apple_touch)

    # 方法 3：核心 SPA 回退
    async def _spa(_req):
        path = _req.path  # [FIX-P0-10] 防止 SPA 回退吞掉 /api/ 和 /ws/ 的 404
        if path.startswith("/api/") or path.startswith("/ws/"):
            return web.json_response({"error": "Not Found"}, status=404)
        resp = web.FileResponse(FRONTEND_DIST / "index.html")
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return resp
    app.router.add_get("/", _spa)
    app.router.add_get("/{tail:.*}", _spa)


# ============================================================
# 启动
# ============================================================
def open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def main():
    app = web.Application()
    app.add_routes(routes)

    # 挂载静态文件与 SPA 回退（必须在 add_routes 之后，让 API 优先匹配）
    setup_static_files(app)

    # 优雅关闭
    async def _on_shutdown(_app):
        await bot_manager.stop_all()

    app.on_shutdown.append(_on_shutdown)

    # 【修复】启动时清空所有实例的 .pid 文件
    # 全新进程不可能有任何 bot 真正在运行，清除残留心跳文件，
    # 避免上一轮留下的文件 mtime 导致 is_instance_running() 误判为"运行中"
    for name in BotInstance.list_instances():
        try:
            inst = BotInstance.load(name)
            _clear_pid(inst.folder)
        except Exception:
            pass

    open_browser()

    print(f"Web GUI 已启动 → http://127.0.0.1:{PORT}")
    web.run_app(app, host="127.0.0.1", port=PORT, print=lambda *a: None)


if __name__ == "__main__":
    main()