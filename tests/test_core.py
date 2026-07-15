import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from utils import (
    clean_for_minecraft, truncate_to_bytes, build_command,
    make_safe_command, make_safe_say, make_safe_me, make_send_text,
    timestamp_to_seconds, get_timestamp,
)
from command_handler import CommandHandler, CommandEntry


# ========== utils ==========

class TestCleanForMinecraft:
    def test_removes_angle_brackets(self):
        assert clean_for_minecraft("<tag>") == "tag"

    def test_removes_square_brackets(self):
        assert clean_for_minecraft("[text]") == "text"

    def test_removes_curly_braces(self):
        assert clean_for_minecraft("{json}") == "json"

    def test_removes_pipe_backtick_backslash_star(self):
        assert clean_for_minecraft("a|b`c\\d*e") == "abcde"

    def test_removes_slash(self):
        assert clean_for_minecraft("/op attacker") == "op attacker"

    def test_replaces_newlines_with_space(self):
        assert clean_for_minecraft("line1\nline2\rline3") == "line1 line2 line3"

    def test_strips_whitespace(self):
        assert clean_for_minecraft("  hello  ") == "hello"

    def test_preserves_normal_text(self):
        assert clean_for_minecraft("Hello, 你好世界！") == "Hello, 你好世界！"


class TestTruncateToBytes:
    def test_short_text_unchanged(self):
        assert truncate_to_bytes("hello", 100) == "hello"

    def test_truncates_with_ellipsis(self):
        result = truncate_to_bytes("hello world", 8)
        assert result.endswith("...")
        assert len(result.encode("utf-8")) <= 8

    def test_ascii_boundary(self):
        assert truncate_to_bytes("abcde", 5) == "abcde"
        assert truncate_to_bytes("abcdef", 5) == "ab..."

    def test_chinese_utf8_boundary(self):
        result = truncate_to_bytes("你好世界", 10)
        assert len(result.encode("utf-8")) <= 10

    def test_too_small_returns_ellipsis(self):
        assert truncate_to_bytes("hello", 3) == "..."


class TestBuildCommand:
    def test_me_mode(self):
        cmd = build_command("hello", 500, mode="me")
        assert cmd.startswith("/me ")

    def test_say_mode(self):
        cmd = build_command("hello", 500, mode="say")
        assert cmd.startswith("/say ")

    def test_raw_mode(self):
        cmd = build_command("hello", 500, mode="raw")
        assert cmd == "hello"

    def test_raw_mode_preserves_command(self):
        cmd = build_command("/op attacker", 500, mode="raw")
        assert cmd == "/op attacker"

    def test_truncation(self):
        cmd = build_command("x" * 600, 100, mode="raw")
        assert len(cmd.encode("utf-8")) <= 100
        assert cmd.endswith("...")

    def test_json_mode(self):
        cmd = build_command("hello", 500, mode="json")
        data = json.loads(cmd)
        assert data["type"] == "chat"
        assert data["body"]["content"] == "hello"

    def test_json_mode_truncation(self):
        cmd = build_command("x" * 500, 100, mode="json")
        data = json.loads(cmd)
        assert data["type"] == "chat"
        assert len(cmd.encode("utf-8")) <= 100


class TestMakeSendText:
    def test_me_mode(self):
        cmd = make_send_text("hello", 500, "me")
        assert cmd.startswith("/me ")

    def test_raw_mode(self):
        cmd = make_send_text("hello", 500, "raw")
        assert cmd == "hello"


class TestTimestampToSeconds:
    def test_valid_timestamp(self):
        ts = timestamp_to_seconds("[2026.5.27/14:30]")
        assert ts > 0

    def test_invalid_timestamp(self):
        assert timestamp_to_seconds("garbage") == 0


# ========== command_handler ==========

class TestCommandHandler:
    def test_empty_commands(self, tmp_path):
        json_file = tmp_path / "commands.json"
        json_file.write_text('{"commands": []}', encoding="utf-8")
        handler = CommandHandler(str(json_file))
        assert handler.match("anything") is None

    def test_match_by_name(self, tmp_path):
        json_file = tmp_path / "commands.json"
        json_file.write_text(
            '{"commands": [{"name": "rules", "aliases": [], "description": "", "response": "rule text", "mode": "me", "admin_only": false}]}',
            encoding="utf-8",
        )
        handler = CommandHandler(str(json_file))
        cmd = handler.match("rules")
        assert cmd is not None
        assert cmd.name == "rules"

    def test_match_by_alias(self, tmp_path):
        json_file = tmp_path / "commands.json"
        json_file.write_text(
            '{"commands": [{"name": "rules", "aliases": ["规则"], "description": "", "response": "rule text", "mode": "me", "admin_only": false}]}',
            encoding="utf-8",
        )
        handler = CommandHandler(str(json_file))
        cmd = handler.match("规则")
        assert cmd is not None
        assert cmd.name == "rules"

    def test_case_insensitive(self, tmp_path):
        json_file = tmp_path / "commands.json"
        json_file.write_text(
            '{"commands": [{"name": "Rules", "aliases": [], "description": "", "response": "text", "mode": "me", "admin_only": false}]}',
            encoding="utf-8",
        )
        handler = CommandHandler(str(json_file))
        assert handler.match("rules") is not None

    def test_missing_file(self):
        handler = CommandHandler("nonexistent.json")
        assert handler.match("anything") is None

    def test_format_response_me(self, tmp_path):
        json_file = tmp_path / "commands.json"
        json_file.write_text(
            '{"commands": [{"name": "test", "aliases": [], "description": "", "response": "hello", "mode": "me", "admin_only": false}]}',
            encoding="utf-8",
        )
        handler = CommandHandler(str(json_file))
        cmd = handler.match("test")
        resp = handler.format_response(cmd)
        assert resp.startswith("/me ")

    def test_format_response_raw(self, tmp_path):
        json_file = tmp_path / "commands.json"
        json_file.write_text(
            '{"commands": [{"name": "test", "aliases": [], "description": "", "response": "hello", "mode": "raw", "admin_only": false}]}',
            encoding="utf-8",
        )
        handler = CommandHandler(str(json_file))
        cmd = handler.match("test")
        resp = handler.format_response(cmd)
        assert resp == "hello"
