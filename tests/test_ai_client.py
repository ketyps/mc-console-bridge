"""ai_client.py 测试：空内容重试、响应结构异常处理。

用假 aiohttp session 模拟 API 响应，不发真实网络请求。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_client import AIClient


class FakeResponse:
    def __init__(self, status, payload, text="err"):
        self.status = status
        self._payload = payload
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class FakeSession:
    closed = False

    def __init__(self, responses):
        self.responses = list(responses)
        self.post_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def post(self, *a, **k):
        self.post_count += 1
        return self.responses.pop(0)


def _client(retry_count=1, responses=None, retry_delay=0):
    c = AIClient(api_key="k", api_url="http://x", model="m",
                 system_prompt="p", retry_count=retry_count, retry_delay=retry_delay)
    c._session = FakeSession(responses or [])
    return c


def _run(coro):
    return asyncio.run(coro)


def _ok(content, finish_reason="stop"):
    return FakeResponse(200, {"choices": [{"message": {"content": content},
                                            "finish_reason": finish_reason}]})


class TestEmptyContentRetry:
    def test_retries_on_empty_content(self):
        async def scenario():
            c = _client(retry_count=1,
                        responses=[_ok("", "length"), _ok("@ketyps 我在这服玩好一阵子啦")])
            reply = await c.get_reply("<ketyps> @bot 你是谁", caller="test", reply_to="ketyps")
            assert reply == "@ketyps 我在这服玩好一阵子啦"
            assert c._session.post_count == 2, "空内容应触发重试"
        _run(scenario())

    def test_fallback_after_all_empty(self):
        async def scenario():
            c = _client(retry_count=1, responses=[_ok("", "length"), _ok("", "length")])
            reply = await c.get_reply("hi", caller="test")
            assert reply == "抱歉，我现在有点问题，稍后再试吧。"
            assert c._session.post_count == 2
        _run(scenario())

    def test_normal_content_no_extra_retry(self):
        async def scenario():
            c = _client(retry_count=2, responses=[_ok("正常回复")])
            reply = await c.get_reply("hi", caller="test")
            assert reply == "正常回复"
            assert c._session.post_count == 1
        _run(scenario())


class TestMalformedResponse:
    def test_missing_choices_retries(self):
        async def scenario():
            c = _client(retry_count=1,
                        responses=[FakeResponse(200, {"choices": []}), _ok("好的")])
            reply = await c.get_reply("hi", caller="test")
            assert reply == "好的"
            assert c._session.post_count == 2
        _run(scenario())
