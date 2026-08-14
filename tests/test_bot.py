"""main.py 核心逻辑测试：sender 解析、冷却、管理员权限、自回声过滤、硬编码规则。

不依赖网络：所有场景走自定义指令路径或直接断言发送内容，不触发 AI API 调用。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import _parse_sender, MinecraftBot
from instance import BotInstance
from ai_client import AIClient


class FakeWS:
    """记录所有 send() 内容的假 WebSocket。"""

    def __init__(self):
        self.sent: list[str] = []

    async def send(self, message):
        self.sent.append(message)


def _make_bot(tmp_path, **overrides):
    """在临时目录创建实例并构造 MinecraftBot（enable_logging=False 避免写盘）。"""
    inst = BotInstance.create("测试服", base_dir=tmp_path)
    for k, v in overrides.items():
        setattr(inst, k, v)
    bot = MinecraftBot(inst, signals=None, runtime={
        "enable_reply": True,
        "enable_auto_comment": False,
        "enable_logging": False,
        "trigger_prefix": inst.trigger_prefix,
        "send_mode": "me",
    })
    return bot, inst


def _run(coro):
    return asyncio.run(coro)


# ========== sender 解析 ==========

class TestParseSender:
    def test_angle_bracket_format(self):
        assert _parse_sender("<Steve> hello", "<{name}>,{name}:") == "Steve"

    def test_colon_format(self):
        assert _parse_sender("Steve: hello", "<{name}>,{name}:") == "Steve"

    def test_system_message_returns_none(self):
        assert _parse_sender("玩家加入了游戏", "<{name}>,{name}:") is None

    def test_template_without_placeholder_skipped(self):
        assert _parse_sender("hello", "no-placeholder") is None

    def test_chinese_name(self):
        assert _parse_sender("<小明> 在吗", "<{name}>,{name}:") == "小明"


# ========== 冷却 ==========

class TestCooldown:
    def test_second_message_within_cooldown_blocked(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path, cooldown_seconds=60)
            ws = FakeWS()
            try:
                await bot._handle_message(ws, "<Steve> @bot 帮助")
                assert ws.sent, "第一条 @bot 应触发指令回复"
                assert "提问" in ws.sent[0]
                n = len(ws.sent)
                await bot._handle_message(ws, "<Steve> @bot 帮助")
                assert len(ws.sent) == n + 1
                assert "服务器正忙" in ws.sent[-1], "冷却期内应返回忙碌提示"
            finally:
                await bot.shutdown()
        _run(scenario())

    def test_different_sender_not_blocked(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path, cooldown_seconds=60)
            ws = FakeWS()
            try:
                await bot._handle_message(ws, "<Steve> @bot 帮助")
                n = len(ws.sent)
                await bot._handle_message(ws, "<Alex> @bot 帮助")
                assert len(ws.sent) == n + 1, "不同玩家应各自独立冷却"
            finally:
                await bot.shutdown()
        _run(scenario())


# ========== 管理员权限 ==========

class TestAdminPermission:
    def test_admin_only_denied_for_regular_player(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path, admin_username="Admin")
            ws = FakeWS()
            try:
                await bot._handle_message(ws, "<Steve> @bot reloadjson")
                assert ws.sent, "应返回拒绝消息"
                assert "没有权限" in ws.sent[-1]
            finally:
                await bot.shutdown()
        _run(scenario())

    def test_admin_only_allowed_for_admin(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path, admin_username="Admin")
            ws = FakeWS()
            try:
                await bot._handle_message(ws, "<Admin> @bot reloadjson")
                assert ws.sent, "管理员应能执行 reloadjson"
                assert "已重载" in ws.sent[-1]
            finally:
                await bot.shutdown()


# ========== 自回声过滤 ==========

class TestSelfEcho:
    def test_own_message_ignored(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path, bot_name="k12")
            ws = FakeWS()
            try:
                await bot._handle_message(ws, "<k12> 我是自己，不要回复")
                assert ws.sent == [], "自己的消息不应触发任何回复"
            finally:
                await bot.shutdown()
        _run(scenario())

    def test_others_message_not_ignored(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path, bot_name="k12")
            ws = FakeWS()
            try:
                await bot._handle_message(ws, "<Steve> @bot 帮助")
                assert ws.sent, "别人的消息应正常触发"
            finally:
                await bot.shutdown()
        _run(scenario())


# ========== Mod 身份握手 ==========

class TestIdentityHandshake:
    def test_identity_sets_player_name(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path)  # 不配置 bot_name
            try:
                await bot._handle_message(FakeWS(), '{"type":"identity","name":"k12"}')
                assert bot._player_name == "k12"
                assert bot._display_name() == "k12"
            finally:
                await bot.shutdown()
        _run(scenario())

    def test_echo_filtered_after_identity(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path)  # 不配置 bot_name，依赖身份握手
            ws = FakeWS()
            try:
                await bot._handle_message(ws, '{"type":"identity","name":"k12"}')
                await bot._handle_message(ws, "<k12> 你好呀！")
                assert ws.sent == [], "身份握手后，自己回复的回声应被过滤，不再重复打印"
            finally:
                await bot.shutdown()
        _run(scenario())

    def test_display_fallback_no_double_brackets(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path)
            try:
                assert bot._display_name() == "未命名"
                assert "<" not in bot._display_name() and ">" not in bot._display_name()
            finally:
                await bot.shutdown()
        _run(scenario())

    def test_identity_not_logged_as_chat(self, tmp_path):
        async def scenario():
            bot, _ = _make_bot(tmp_path)
            ws = FakeWS()
            try:
                await bot._handle_message(ws, '{"type":"identity","name":"k12"}')
                assert ws.sent == []
                assert len(bot.global_chat_context) == 0, "身份握手不应进入聊天上下文"
            finally:
                await bot.shutdown()
        _run(scenario())


# ========== AI 硬编码规则（@提问者）==========

class TestHardcodedRules:
    @staticmethod
    def _client():
        return AIClient(api_key="", api_url="http://x", model="m", system_prompt="你是玩家")

    def test_reply_to_rule_in_prompt(self):
        msgs = self._client()._build_messages("hello", None, reply_to="Steve")
        content = msgs[0]["content"]
        assert "每次回复都必须以 @提问者名字 开头" in content, "硬编码规则 7 应存在"
        assert "本条消息的提问者是「Steve」，你的回复必须以 @Steve 开头。" in content, \
            "显式提问者提示应注入"

    def test_no_reply_to_no_explicit_hint(self):
        msgs = self._client()._build_messages("hello", None)
        content = msgs[0]["content"]
        assert "本条消息的提问者是" not in content, "无提问者时不应注入提示"
        assert "每次回复都必须以 @提问者名字 开头" in content, "规则本身仍在"

    def test_rules_append_after_user_prompt(self):
        client = self._client()
        msgs = client._build_messages("hello", "自定义人设", reply_to="Steve")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"].startswith("自定义人设")
        assert "硬编码规则" in msgs[0]["content"]

    def test_message_tail_is_user_message(self):
        msgs = self._client()._build_messages("你好", None, reply_to="Steve")
        assert msgs[-1] == {"role": "user", "content": "你好"}
