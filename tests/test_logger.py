"""logger.py 测试：写入、HTML 转义、关闭幂等、同步生成。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import ChatLogger, _line_html


class TestChatLogger:
    def test_write_creates_total_txt(self, tmp_path):
        log = ChatLogger(str(tmp_path / "logs"))
        try:
            log.write("[2026.8.14/14:00] <Steve> 你好", "user_atbot")
            content = (tmp_path / "logs" / "chat_log.txt").read_text(encoding="utf-8")
            assert "你好" in content
            assert content.rstrip().endswith("你好")
        finally:
            log.close()

    def test_write_appends_multiple_lines(self, tmp_path):
        log = ChatLogger(str(tmp_path / "logs"))
        try:
            log.write("第一行", "info")
            log.write("第二行", "info")
            lines = (tmp_path / "logs" / "chat_log.txt").read_text(encoding="utf-8").splitlines()
            assert lines == ["第一行", "第二行"]
        finally:
            log.close()

    def test_close_idempotent(self, tmp_path):
        log = ChatLogger(str(tmp_path / "logs"))
        log.write("x", "info")
        log.close()
        log.close()  # 重复调用不应抛异常

    def test_line_html_escapes_special_chars(self):
        html = _line_html('<script>alert("x")</script>', "raw", 0.0)
        assert "&lt;script&gt;" in html
        assert "<script>" not in html
        assert "alert" in html

    def test_sync_generates_html_and_day_files(self, tmp_path):
        log = ChatLogger(str(tmp_path / "logs"))
        try:
            log.write("[2026.8.14/14:00] 你好", "user_atbot")
            result = log.sync()
            assert result["total_lines"] >= 1
            assert (tmp_path / "logs" / "chat_log.html").exists()
            # 按天文件
            day_files = list((tmp_path / "logs" / "txt").glob("chat_log_*.txt"))
            html_files = list((tmp_path / "logs" / "html").glob("chat_log_*.html"))
            assert len(day_files) >= 1 and len(html_files) >= 1
        finally:
            log.close()
