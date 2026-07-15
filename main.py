# Refactor: 完整 raw_msg 透传 + Fixed: BUG-B, BUG-E, bot 身份注入, P0-P3 design issues, 泛用性改造
"""MinecraftBot — 核心机器人，通过 WebSocket 连接 Minecraft 服务器。"""
import asyncio
import ctypes
import json  # [FIX-P0-1] 顶层 import，供 _send_worker 中 json.loads 使用
import os
import re
import sys
import time
from collections import deque
from pathlib import Path

import websockets
from colorama import init, Fore, Style
init()

from utils import get_timestamp, clean_for_minecraft, make_safe_command, make_send_text
from ai_client import AIClient
from logger import ChatLogger, merge_old_log
from command_handler import CommandHandler


# ========== 跨进程 PID 检测 ==========

def _write_pid(instance_folder: Path) -> None:
    (instance_folder / ".pid").write_text(str(os.getpid()))

def _touch_pid(instance_folder: Path) -> None:
    """更新心跳时间戳，每 5 秒调用一次。"""
    pid_file = instance_folder / ".pid"
    if pid_file.exists():
        try:
            pid_file.touch()
        except OSError:
            pass


def _clear_pid(instance_folder: Path) -> None:
    pid_file = instance_folder / ".pid"
    if pid_file.exists():
        pid_file.unlink()


def is_instance_running(instance_name: str) -> bool:
    """检查实例的 .pid 文件：心跳在 30 秒内 + PID 存活才认为运行中。"""
    from instance import BotInstance
    try:
        inst = BotInstance.load(instance_name)
    except Exception:
        return False
    pid_file = inst.folder / ".pid"
    if not pid_file.exists():
        return False
    # 心跳超时检测
    if time.time() - pid_file.stat().st_mtime > 30:
        _clear_pid(inst.folder)
        return False
    try:
        pid = int(pid_file.read_text().strip().split("\n")[0])
    except (ValueError, OSError):
        _clear_pid(inst.folder)
        return False
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x0400, 0, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        _clear_pid(inst.folder)
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            _clear_pid(inst.folder)
            return False


# _parse_sender: 基于 template 模式串动态编译正则
# 缓存编译好的正则列表，避免每次调用都重新编译
_sender_pattern_cache: dict[str, list[re.Pattern]] = {}


def _compile_sender_patterns(sender_patterns: str) -> list[re.Pattern]:
    """将逗号分隔的模板（如 <{name}>,{name}:）编译为 re.Pattern 列表。

    每个模板中必须有且只处理第一个 {name} 占位符。
    无效模板（缺少 {name}、编译失败）跳过并打印 WARN。
    """
    patterns: list[re.Pattern] = []
    for template in sender_patterns.split(","):
        template = template.strip()
        if not template:
            continue
        if "{name}" not in template:
            print(f"[WARN] 发送者格式模板 '{template}' 缺少 {{name}} 占位符，已跳过")
            continue
        prefix, suffix = template.split("{name}", 1)
        # 字面部分用 re.escape，{name} 替换为捕获组
        pattern_str = re.escape(prefix) + "(.+?)" + re.escape(suffix)
        try:
            patterns.append(re.compile(pattern_str))
        except re.error as e:
            print(f"[WARN] 发送者格式模板 '{template}' 编译失败: {e}，已跳过")
    return patterns


def _parse_sender(raw_msg: str, sender_patterns: str) -> str | None:
    """从原始聊天消息中提取发言者名字。

    基于可配置的 sender_patterns（逗号分隔的模板列表）依次尝试匹配。
    返回提取到的玩家名（strip 后），全失败返回 None。
    """
    if sender_patterns not in _sender_pattern_cache:
        _sender_pattern_cache[sender_patterns] = _compile_sender_patterns(sender_patterns)

    for pattern in _sender_pattern_cache[sender_patterns]:
        m = pattern.match(raw_msg)
        if m:
            return m.group(1).strip()
    return None


class MinecraftBot:
    """Minecraft AI 聊天机器人。

    参数:
        instance: BotInstance — 所有实例级配置
        signals:  BotSignals — Qt 信号，用于 GUI 更新（CLI 模式可传 None）
        runtime:  dict — 高频切换项，key: enable_reply, enable_auto_comment,
                         enable_logging, trigger_prefix, send_mode
    """

    def __init__(self, instance, signals=None, runtime=None):
        self.instance = instance
        self.signals = signals
        self.runtime = runtime or {}

        # 从 runtime 读取高频设置，提供默认值
        self.enable_reply = self.runtime.get("enable_reply", False)
        self.enable_logging = self.runtime.get("enable_logging", True)
        self.enable_auto_comment = self.runtime.get("enable_auto_comment", False)
        self.trigger_prefix = self.runtime.get("trigger_prefix", instance.trigger_prefix)
        # [FIX-P0-6] 空 trigger_prefix 会使所有消息触发回复，必须兜底
        if not self.trigger_prefix:
            print("[WARN] trigger_prefix 为空，已回退为 @bot")
            self.trigger_prefix = "@bot"
        self.send_mode = self.runtime.get("send_mode", instance.send_mode)

        # 初始化子模块
        # 若配置了 BOT_NAME，在系统提示词前动态注入身份声明
        # 不使用 instance.name 作为 fallback——instance.name 是文件夹名，不是游戏内 ID
        bot_name = instance.bot_name
        if bot_name:
            identity_prefix = (
                f"你在这个服务器中的玩家名是「{bot_name}」，这是你自己的账号。\n"
                f"当聊天消息里出现「{bot_name}」时，说的就是你自己，不要用第三人称引用自己。\n\n"
            )
            resolved_system_prompt = identity_prefix + instance.system_prompt
        else:
            # BOT_NAME 未配置：跳过注入，不注入错误信息
            resolved_system_prompt = instance.system_prompt

        self.ai = AIClient(
            api_key=instance.deepseek_api_key,
            api_url=instance.deepseek_api_url,
            model=instance.model_flash,
            system_prompt=resolved_system_prompt,
            max_history=instance.max_history,
            api_timeout=instance.api_timeout,
            temperature=instance.temperature,
            max_tokens=instance.max_tokens,
            retry_count=instance.retry_count,
            retry_delay=instance.retry_delay,
        )
        self.logger = ChatLogger(
            log_dir=str(instance.folder / instance.log_dir),
        )
        self.command_handler = CommandHandler(
            commands_file=instance.folder / "custom_commands.json",
            max_command_bytes=instance.max_command_bytes,
        )

        # 内部队列与事件
        self._outbox_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._trigger_comment = asyncio.Event()
        self._trigger_reply_recent = asyncio.Event()

        # 运行时状态
        # [FIX-P0-12] 原来 maxlen 和"过滤 @bot 后要求的最少行数"用了同一个值，
        # 只要窗口内出现过一条 @bot 消息，过滤后就必然凑不够，导致氛围评论永远被跳过。
        # 这里把原始滑动窗口放大到 3 倍，留出被过滤掉的余量；过滤后的判断阈值（global_context_size）本身不变。
        self.global_chat_context: deque[str] = deque(maxlen=instance.global_context_size * 3)
        self.prev_context_lines: list[str] | None = None
        self._shutdown = False

        # 速率限制（每个玩家独立计时）
        # 使用 dict 记录每个玩家的最后回复时间，key 为小写玩家名。
        # 在典型 Minecraft 服务器中同时活跃的玩家数量有限（通常 < 50），
        # 因此不会无限增长，不做定期清理。若需要极限场景下的内存安全，
        # 可将来加一个 LRU 或定期清理逻辑。
        self._last_reply_time: dict[str, float] = {}
        self._cooldown_seconds: int = instance.cooldown_seconds

    # ========== 公共方法（GUI 调用，线程安全）==========

    def send_raw_command(self, text: str, mode: str = "me") -> None:
        """从 GUI 发送栏入队一条消息。"""
        safe = clean_for_minecraft(text)
        command = make_send_text(safe, self.instance.max_command_bytes, mode)
        try:
            self._outbox_queue.put_nowait(command)
        except asyncio.QueueFull:
            self._print("[WARN] 发送队列已满，消息被丢弃")

    def trigger_comment(self) -> None:
        """手动触发一次氛围评论。"""
        self._trigger_comment.set()

    def trigger_reply_recent(self) -> None:
        """手动触发一次对最近消息的回复。"""
        self._trigger_reply_recent.set()

    def update_runtime(self, **kwargs) -> None:
        """热更新运行时设置（无需重启）。"""
        for key in ("enable_reply", "enable_auto_comment", "enable_logging",
                     "trigger_prefix", "send_mode"):
            if key in kwargs:
                setattr(self, key, kwargs[key])
        # [FIX-P0-6] runtime 热更新也可能传入空 trigger_prefix，同样需要兜底
        if not self.trigger_prefix:
            print("[WARN] trigger_prefix 为空，已回退为 @bot")
            self.trigger_prefix = "@bot"

    def queue_send(self, text: str, use_prefix: bool = False) -> None:
        """将消息加入发送队列（GUI 控制台用）。

        use_prefix: 勾选后在消息前加上 reply_prefix。
        """
        if use_prefix:
            text = self.instance.reply_prefix + text
        command = make_send_text(text, self.instance.max_command_bytes, self.send_mode)
        try:
            self._outbox_queue.put_nowait(command)
        except asyncio.QueueFull:
            self._print("[WARN] 发送队列已满，消息被丢弃")

    def switch_model(self, target: str) -> str:
        """从 GUI 控制台直接切换模型（pro/flash），效果与游戏内
        switch pro / switch flash 指令一致：切换模型、在游戏里广播确认消息、
        写入日志。返回切换后的模型名。"""
        if target not in ("pro", "flash"):
            raise ValueError(f"未知模型档位: {target}")
        old = self.ai.model
        self.ai.model = self.instance.model_pro if target == "pro" else self.instance.model_flash
        sp = self.instance.system_msg_prefix
        msg = f"{sp}已从 {old} 切换到 {self.ai.model}"
        command = make_send_text(msg, self.instance.max_command_bytes, self.send_mode)
        try:
            self._outbox_queue.put_nowait(command)
        except asyncio.QueueFull:
            self._print("[WARN] 发送队列已满，消息被丢弃")
        self._emit(f"{get_timestamp()} [系统] 已从 {old} 切换到 {self.ai.model}", "info")
        if self.signals:
            self.signals.model_changed.emit(self.ai.model)
        return self.ai.model

    # ========== 日志辅助 ==========

    def _emit(self, line: str, msg_type: str = "raw"):
        """同时写文件和发 Qt 信号（CLI 模式直接打印到终端）。"""
        if self.enable_logging:
            try:
                self.logger.write(line, msg_type)
            except Exception as e:
                # 【修复】防止日志写入失败导致异常冒泡，保证消息能正常输出到控制台
                # 这里直接使用 print 避免引发二次递归
                print(f"[CRITICAL] 日志写入失败，请检查文件权限或磁盘空间: {e}")

        if self.signals:
            self.signals.log_line.emit(line, msg_type)
        else:
            self._print(line)

    def _print(self, line: str, color: str = ""):
        """控制台输出。CLI 模式打印到 stdout，GUI 模式通过信号转发。"""
        if self.signals is None:
            safe = line.encode('gbk', errors='replace').decode('gbk')
            print(f"{color}{safe}{Style.RESET_ALL}" if color else safe)
        else:
            self.signals.log_line.emit(line, "info")

    # ========== 消息处理 ==========

    async def _handle_message(self, websocket, raw_msg: str):
        ts = get_timestamp()

        # 【修复】自身回音检测提前 — 在记录日志之前判断，避免 bot 自己的回复
        # 被服务器广播回来后先记一遍日志再丢弃，造成控制台重复打印
        # [FIX-P0-2] is_self_echo 检测只能用真实的 bot_name，不能兜底
        # folder 名（instance.name）不能代表游戏内 ID，否则自身回音检测失效
        bot_name = self.instance.bot_name
        is_self_echo = bool(bot_name) and any(
            raw_msg.startswith(prefix) for prefix in [
                f"<{bot_name}>",
                f"* {bot_name} ",
                f"[{bot_name}]",
            ]
        )
        if is_self_echo:
            return

        # 跳过 MC 服务器握手消息（协议层细节，对用户无意义）
        if raw_msg.startswith('{"type":"communicationType"'):
            return

        # 收到的每条消息（非自回声、非握手）都先打印到日志
        _trigger_in_msg = (self.trigger_prefix in raw_msg) or \
                          (self.trigger_prefix in raw_msg.replace("＠", "@"))
        _incoming_type = "user_atbot" if _trigger_in_msg else "raw"
        self._emit(f"{ts} {raw_msg}", _incoming_type)

        # 根据配置跳过特定前缀的消息（各服务器插件协议不同，由用户自行配置）
        if self.instance.skip_msg_prefix:
            prefixes = [p.strip() for p in self.instance.skip_msg_prefix.split(",") if p.strip()]
            if any(raw_msg.startswith(p) for p in prefixes):
                return

        # 归一化全角 @
        raw_msg = raw_msg.replace("＠", "@")

        self.global_chat_context.append(raw_msg)

        if not self.enable_reply:
            return

        trigger_pos = raw_msg.find(self.trigger_prefix)
        if trigger_pos == -1:
            return

        # 仍提取 trigger 之后的内容，用于：指令匹配 + 空消息检测
        # 但传给 AI 的是完整 raw_msg
        user_message = raw_msg[trigger_pos + len(self.trigger_prefix):].strip()
        if not user_message:
            command = make_send_text(
                f"{self.instance.system_msg_prefix}请说点什么吧～", self.instance.max_command_bytes, self.send_mode)
            command = self._clean_command(command)
            await websocket.send(command)
            return

        # 速率限制（每个玩家独立）
        sender_name = _parse_sender(raw_msg, self.instance.sender_patterns)
        # 冷却用 "__unknown__" 兜底：解析失败的消息之间共享全局冷却，不会不限速
        sender_key = (sender_name or "__unknown__").lower()
        now = time.time()
        last_time = self._last_reply_time.get(sender_key, 0.0)
        if now - last_time < self._cooldown_seconds:
            remaining = int(self._cooldown_seconds - (now - last_time))
            command = make_send_text(
                f"{self.instance.system_msg_prefix}服务器正忙，请 {remaining} 秒后再试～",
                self.instance.max_command_bytes, self.send_mode)
            command = self._clean_command(command)
            await websocket.send(command)
            self._emit(f"{get_timestamp()} [系统] {sender_key} 触发冷却，剩余 {remaining} 秒", "info")
            return
        self._last_reply_time[sender_key] = now

        # 自定义指令（包括带 action 的内置指令，如 switch_pro / switch_flash / show_model）
        cmd = self.command_handler.match(user_message)
        if cmd is not None:
            # 【Bug 1】admin_only 权限检查：解析失败（None）时拒绝，宁拦勿放
            if cmd.admin_only:
                admin_names = [a.lower() for a in self.instance.admin_list]
                if sender_name is None or sender_name.lower() not in admin_names:
                    command = make_send_text(
                        f"{self.instance.system_msg_prefix}§c你没有权限使用该指令",
                        self.instance.max_command_bytes, self.send_mode)
                    command = self._clean_command(command)
                    await websocket.send(command)
                    self._emit(f"{get_timestamp()} [系统] {sender_name} 尝试使用无权限指令 [{cmd.name}]", "warn")
                    return

            if cmd.action == "switch_pro":
                old = self.ai.model
                self.ai.model = self.instance.model_pro
                sp = self.instance.system_msg_prefix
                msg = f"{sp}已从 {old} 切换到 {self.ai.model}"
                command = make_send_text(msg, self.instance.max_command_bytes, self.send_mode)
                command = self._clean_command(command)
                await websocket.send(command)
                self._emit(f"{get_timestamp()} [系统] 已从 {old} 切换到 {self.ai.model}", "info")
            elif cmd.action == "switch_flash":
                old = self.ai.model
                self.ai.model = self.instance.model_flash
                sp = self.instance.system_msg_prefix
                msg = f"{sp}已从 {old} 切换到 {self.ai.model}"
                command = make_send_text(msg, self.instance.max_command_bytes, self.send_mode)
                command = self._clean_command(command)
                await websocket.send(command)
                self._emit(f"{get_timestamp()} [系统] 已从 {old} 切换到 {self.ai.model}", "info")
            elif cmd.action == "show_model":
                sp = self.instance.system_msg_prefix
                command = make_send_text(
                    f"{sp}当前模型: {self.ai.model}", self.instance.max_command_bytes, self.send_mode)
                command = self._clean_command(command)
                await websocket.send(command)
                self._emit(f"{get_timestamp()} [系统] 当前模型: {self.ai.model}", "info")
            elif cmd.action == "reload_commands":
                # 【Bug 2】真正的重载逻辑
                sp = self.instance.system_msg_prefix
                success, count = self.command_handler.reload()
                if success:
                    msg = f"{sp}自定义指令已重载（{count} 条指令）"
                    clean_msg = f"自定义指令已重载（{count} 条指令）"
                else:
                    msg = f"{sp}§c重载失败，指令文件可能有格式错误，已保留原有指令"
                    clean_msg = "重载失败，指令文件可能有格式错误，已保留原有指令"
                command = make_send_text(msg, self.instance.max_command_bytes, self.send_mode)
                command = self._clean_command(command)
                await websocket.send(command)
                self._emit(f"{get_timestamp()} [系统] {clean_msg}", "info")
                self._print(f"重载指令: {'成功' if success else '失败'} ({count} 条)", Fore.LIGHTYELLOW_EX)
            else:
                # 静态回复
                response = self.command_handler.format_response(cmd)
                response = self._clean_command(response)
                await websocket.send(response)
                self._emit(f"{get_timestamp()} [系统] 执行指令 [{cmd.name}]: {response}", "info")
                self._print(f"执行指令 [{cmd.name}]: {response}", Fore.LIGHTYELLOW_EX)
            return

        # AI 回复
        # 传入完整原始消息，让 AI 自行理解语境和发送者
        reply = await self.ai.get_reply(raw_msg, caller="普通@bot回复")
        if "有点问题" in reply or "有点慢" in reply:
            err = getattr(self.ai, "last_error", "未知错误")
            self._emit(f"{get_timestamp()} [系统] AI 调用失败: {err}", "error")
        safe_reply = clean_for_minecraft(reply)
        command = make_safe_command(
            self.instance.reply_prefix, safe_reply,
            self.instance.max_command_bytes, self.send_mode)
        _bot = self.instance.bot_name or "<未命名>"  # [FIX-P0-2] 展示兜底，不影响 MC 发送
        _bot_prefix = f"* {_bot}" if self.send_mode == "me" else f"<{_bot}>"
        self._emit(f"{get_timestamp()} {_bot_prefix} {self.instance.reply_prefix}{safe_reply}", "robot_reply")
        command = self._clean_command(command)
        await websocket.send(command)

    # ========== 额外回复 ==========

    async def _reply_recent_worker(self, websocket):
        """等待手动触发，对最近三条聊天消息生成 AI 回复。"""
        while not self._shutdown:
            await self._trigger_reply_recent.wait()
            self._trigger_reply_recent.clear()
            msgs = list(self.global_chat_context)[-3:]
            if len(msgs) == 0:
                self._print("[回复最近] 暂无聊天消息")
                continue
            context = "\n".join(msgs)
            prompt = (
                "请根据以下最近几条聊天消息，以一个玩家的身份做一个简短自然的回复，"
                "语气活泼友好。"
                "硬编码规则：当你需要在回复中提及服务器里的其他玩家名字时，"
                "请务必在名字前面加上 @ 符号。"
                f"\n{context}"
            )
            try:
                reply = await self.ai.get_reply(prompt, save_history=False, caller="手动触发回复")
            except Exception as e:
                self._emit(f"{get_timestamp()} [系统] 追加回复失败: {e}", "error")
                continue
            safe = clean_for_minecraft(reply)
            command = make_safe_command(
                self.instance.reply_prefix, safe,
                self.instance.max_command_bytes, self.send_mode,
            )
            _bot = self.instance.bot_name or "<未命名>"  # [FIX-P0-2] 展示兜底，不影响 MC 发送
            _bot_prefix = f"* {_bot}" if self.send_mode == "me" else f"<{_bot}>"
            self._emit(f"{get_timestamp()} [手动触发回复]{_bot_prefix}  {self.instance.reply_prefix}{safe}", "robot_reply")
            try:
                command = self._clean_command(command)
                await websocket.send(command)
            except websockets.ConnectionClosed:
                self._print("🔌 发送追加回复时 WebSocket 已关闭")
                return

    # ========== 氛围评论 ==========

    async def _auto_comment_loop(self, websocket):
        try:
            while not self._shutdown:
                try:
                    await asyncio.wait_for(
                        self._trigger_comment.wait(),
                        timeout=self.instance.auto_comment_interval,
                    )
                    manual = True
                    self._trigger_comment.clear()
                    self._print("🖐️ 手动触发氛围评论")
                except asyncio.TimeoutError:
                    manual = False

                if self._shutdown:
                    return
                if not manual and not self.enable_auto_comment:
                    continue

                curr = list(self.global_chat_context)
                if len(curr) < self.instance.global_context_size:
                    self._print(f"⏭️ 消息数 {len(curr)} < {self.instance.global_context_size}，跳过")
                    continue

                if not manual and self.prev_context_lines is not None and curr == self.prev_context_lines:
                    self._print("⏭️ 最近消息与上次触发时完全一致（无新消息），跳过氛围评论")
                    continue

                self._print(f"⏰ 触发氛围评论，基于最近 {len(curr)} 条消息")
                # 过滤掉 @bot 提问，避免氛围评论重复回复同一个问题
                ctx_lines = [l for l in curr if self.trigger_prefix not in l]
                if len(ctx_lines) < self.instance.global_context_size:
                    # [FIX-P0-12] 补上具体数字，避免日志看不出到底差多少条
                    self._print(f"⏭️ 过滤 @bot 后消息数 {len(ctx_lines)} < {self.instance.global_context_size}，跳过")
                    self.prev_context_lines = curr
                    continue
                context_text = "\n".join(ctx_lines)
                prompt = (
                    "请根据最近服务器里的这几条聊天消息，做一个综合性的简短评论，"
                    "像朋友闲聊一样，语气活泼自然，不要提及具体玩家（除非有必要），"
                    "但要体现对聊天内容的感知。"
                    "硬编码规则：当你需要在回复中提及服务器里的其他玩家名字时，"
                    "请务必在名字前面加上 @ 符号。"
                    f"\n{context_text}"
                )
                reply = await self.ai.get_reply(
                    prompt, system_prompt=self.instance.auto_comment_prompt,
                    save_history=False, caller="氛围评论",
                )
                safe_reply = clean_for_minecraft(reply)

                final = f"{self.instance.comment_prefix}{safe_reply}"
                command = make_safe_command(
                    "", final, self.instance.max_command_bytes, self.send_mode)

                self._print(f"📏 {len(command.encode('utf-8'))}/{self.instance.max_command_bytes}")
                _bot = self.instance.bot_name or "<未命名>"  # [FIX-P0-2] 展示兜底，不影响 MC 发送
                _bot_prefix = f"* {_bot}" if self.send_mode == "me" else f"<{_bot}>"
                self._emit(f"{get_timestamp()} [感知]{_bot_prefix}  {final}", "perception_reply")  # [FIX-P0-16] 氛围评论单独用独立 msg_type，前端可单独上色
                try:
                    command = self._clean_command(command)
                    await websocket.send(command)
                except websockets.ConnectionClosed:
                    self._print("🔌 发送氛围评论时 WebSocket 已关闭")
                    return

                self.prev_context_lines = curr

        except asyncio.CancelledError:
            pass

    # ========== 发送前净化 ==========

    def _clean_command(self, command: str) -> str:
        """发送前对命令内容做最终净化，防止控制字符、零宽字符等导致被踢出。
        §（颜色码）和 [] 不受此方法过滤（可能在 reply_prefix / comment_prefix 等
        可信配置中出现）；AI 正文在拼接前已由 clean_for_minecraft 清理。
        只清理内容部分，保留 /me / /say 命令前缀本身。
        """
        import json as _json
        if command.startswith("/me "):
            return "/me " + clean_for_minecraft(command[4:])
        if command.startswith("/say "):
            return "/say " + clean_for_minecraft(command[5:])
        if command.startswith("{"):
            try:
                data = _json.loads(command)
                if "body" in data and "content" in data["body"]:
                    data["body"]["content"] = clean_for_minecraft(
                        data["body"]["content"])
                    return _json.dumps(data, ensure_ascii=False)
            except Exception:
                pass
        # raw 模式或其他
        return clean_for_minecraft(command)

    # ========== GUI 消息发送工作线程 ==========

    async def _send_worker(self, ws):
        try:
            while not self._shutdown:
                try:
                    command = await asyncio.wait_for(
                        self._outbox_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    command = self._clean_command(command)
                    # 解析显示用文本（去掉命令前缀）
                    if command.startswith("/me "):
                        display_text = command[4:]
                    elif command.startswith("/say "):
                        display_text = command[5:]
                    elif command.startswith("{"):
                        try:
                            display_text = json.loads(command).get("body", {}).get("content", command)
                        except Exception:
                            display_text = command
                    else:
                        display_text = command
                    _bot = self.instance.bot_name or "<未命名>"  # [FIX-P0-2] 展示兜底，不影响 MC 发送
                    _bot_prefix = f"* {_bot}" if command.startswith("/me ") else f"<{_bot}>"
                    self._emit(f"{get_timestamp()} {_bot_prefix} {display_text}", "robot_reply")
                    await ws.send(command)
                except websockets.ConnectionClosed:
                    self._print("[GUI] 发送失败：WebSocket 已关闭")
                    break
        except asyncio.CancelledError:
            pass

    # ========== 主循环 ==========

    async def _heartbeat(self):
        """每 5 秒刷新 PID 文件时间戳，供跨进程检测用。"""
        while not self._shutdown:
            await asyncio.sleep(5)
            _touch_pid(self.instance.folder)

    async def run(self):
        _write_pid(self.instance.folder)
        log_dir = self.instance.folder / self.instance.log_dir
        merge_old_log(
            old_log_file=str(self.instance.folder / "chat_log.txt"),
            total_log_file=str(log_dir / "chat_log.html"),
        )

        self.ai.set_context(self.global_chat_context)
        first_connect = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

        while not self._shutdown:
            try:
                async with websockets.connect(self.instance.ws_url) as ws:
                    bot = self.instance.bot_name or "<未命名>"  # [FIX-P0-2] 展示兜底，不影响 MC 发送
                    model = self.ai.model or "?"
                    ts = get_timestamp()
                    if first_connect:
                        self._print(f"{ts} 已连接 {bot} | {model} ({self.instance.ws_url})")
                        first_connect = False
                    else:
                        self._print(f"{ts} 已重连 {bot} | {model} ({self.instance.ws_url})")
                    if self.signals:
                        self.signals.ws_connected.emit(True)

                    self.global_chat_context.clear()
                    self.prev_context_lines = None
                    self.ai.clear_history()

                    comment_task = asyncio.create_task(self._auto_comment_loop(ws))
                    send_task = asyncio.create_task(self._send_worker(ws))
                    reply_recent_task = asyncio.create_task(self._reply_recent_worker(ws))

                    loop = asyncio.get_running_loop()
                    last_msg = {"t": loop.time()}

                    async def heartbeat():
                        while True:
                            await asyncio.sleep(self.instance.heartbeat_check_interval)
                            if (asyncio.get_running_loop().time() - last_msg["t"]
                                    > self.instance.heartbeat_timeout):
                                self._print("⏰ 超时无消息，主动断开重连...")
                                await ws.close()
                                return

                    hb_task = asyncio.create_task(heartbeat())

                    try:
                        async for msg in ws:
                            last_msg["t"] = asyncio.get_running_loop().time()
                            try:
                                await self._handle_message(ws, msg)
                            except Exception as ex:
                                self._emit(f"{get_timestamp()} [系统] 处理消息失败: {ex}", "error")
                    except (websockets.ConnectionClosed, Exception) as e:
                        hb_task.cancel()
                        try:
                            await hb_task
                        except asyncio.CancelledError:
                            pass

                        if isinstance(e, websockets.ConnectionClosed):
                            self._print(f"🔌 连接断开，{self.instance.reconnect_delay}s 后重连...")
                            self._emit(f"连接断开于 {get_timestamp()}", "separator")
                        else:
                            self._print(f"[WARN] 错误: {e}，{self.instance.reconnect_delay}s 后重连...")
                            self._emit(f"错误: {e}", "separator")
                    finally:
                        comment_task.cancel()
                        send_task.cancel()
                        reply_recent_task.cancel()
                        try:
                            await comment_task
                        except asyncio.CancelledError:
                            pass
                        try:
                            await send_task
                        except asyncio.CancelledError:
                            pass
                        try:
                            await reply_recent_task
                        except asyncio.CancelledError:
                            pass

                    if self.signals:
                        self.signals.ws_connected.emit(False)
                    await asyncio.sleep(self.instance.reconnect_delay)

            except ConnectionRefusedError as e:
                msg = f"[ERROR] 拒绝连接 {self.instance.ws_url} — 请确认："
                self._print(msg)
                self._print(f"  1) Minecraft 服务器是否正在运行？")
                self._print(f"  2) WebSocket 插件已安装并监听正确端口？")
                self._print(f"  3) WS_URL 配置是否正确？（当前: {self.instance.ws_url}）")
                self._print(f"  ↓ 原始错误: {e}")
                self._print(f"  {self.instance.reconnect_delay_long}s 后重试...")
                if self.signals:
                    self.signals.status_message.emit(f"{msg} 见控制台")
                await asyncio.sleep(self.instance.reconnect_delay_long)
            except OSError as e:
                msg = f"[ERROR] 网络错误: {e}"
                self._print(msg)
                self._print(f"  {self.instance.reconnect_delay_long}s 后重试...")
                if self.signals:
                    self.signals.status_message.emit(msg)
                await asyncio.sleep(self.instance.reconnect_delay_long)
            except Exception as e:
                msg = f"[ERROR] 连接失败 ({type(e).__name__}): {e}"
                self._print(msg)
                self._print(f"  {self.instance.reconnect_delay_long}s 后重试...")
                if self.signals:
                    self.signals.status_message.emit(msg)
                await asyncio.sleep(self.instance.reconnect_delay_long)

    async def shutdown(self):
        """优雅停止机器人。"""
        self._shutdown = True
        hb = getattr(self, "_heartbeat_task", None)
        if hb and not hb.done():
            hb.cancel()
        self.logger.close()
        await self.ai.close()
        _clear_pid(self.instance.folder)
        self._print("bot stopped.")
        if self.signals:
            self.signals.stopped.emit()


# ========== CLI 入口（python main.py）==========
if __name__ == "__main__":
    import sys
    from instance import BotInstance

    async def _cli_main():
        names = BotInstance.list_instances()
        if not names:
            print("没有可用实例。创建: python manage.py create <名称>")
            return
        if len(sys.argv) > 1:
            name = sys.argv[1]
        else:
            name = names[0]
            if len(names) > 1:
                print(f"可用实例: {', '.join(names)}  (默认 {name})")
        instance = BotInstance.load(name)
        runtime = {
            "enable_reply": False, "enable_auto_comment": False,
            "enable_logging": True,
            "trigger_prefix": instance.trigger_prefix,
            "send_mode": instance.send_mode,
        }
        bot = MinecraftBot(instance, signals=None, runtime=runtime)
        try:
            await bot.run()
        except KeyboardInterrupt:
            pass
        finally:
            await bot.shutdown()

    asyncio.run(_cli_main())