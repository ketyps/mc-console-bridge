import html as _html
import os
import re
import shutil
import time as _time
from collections import deque
from datetime import datetime
from pathlib import Path

from utils import timestamp_to_seconds

RING_BUFFER_SIZE = 200

# ========== HTML 模板 ==========
HTML_STYLE = """
        body { background-color: #1e1e1e; color: #ccc; font-family: 'Consolas', 'Courier New', monospace; padding: 10px; margin-top: 100px; }
        .highlight { background-color: #ffff00; color: #000; }
        #search-container {
            position: fixed; top: 0; left: 0; width: 100%;
            background: #333; padding: 8px; z-index: 1000;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
            display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
        }
        #search-container input, #search-container button {
            padding: 5px 10px; border: 1px solid #555;
            background: #222; color: #fff; border-radius: 3px;
        }
        #search-container button { cursor: pointer; background: #555; }
        #search-container button:hover { background: #777; }
        #time-range { display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
        #search-nav { display: flex; gap: 2px; }
        #search-nav button { padding: 5px 8px; }
        #match-counter { color: #ccc; margin-left: 5px; }
        #jump-to { display: flex; gap: 5px; align-items: center; }
        #matchIndex { width: 60px; text-align: center; }
        .hidden { display: none; }
"""

HTML_SCRIPT = """
        let currentMatchIndex = -1, visibleLines = [], allLines = [];
        function filterByTimeRange() {
            const startStr = document.getElementById('startTime').value.trim();
            const endStr = document.getElementById('endTime').value.trim();
            const start = startStr ? new Date(startStr.replace('/', ' ').replace(/\\./g, '-')).getTime() / 1000 : 0;
            const end = endStr ? new Date(endStr.replace('/', ' ').replace(/\\./g, '-')).getTime() / 1000 : Infinity;
            document.querySelectorAll('.log-line').forEach(line => {
                const ts = parseFloat(line.dataset.timestamp);
                line.classList.toggle('hidden', ts < start || ts > end);
            });
            updateVisibleLines(); updateSearch();
        }
        function clearTimeRange() {
            document.getElementById('startTime').value = '';
            document.getElementById('endTime').value = '';
            document.querySelectorAll('.log-line').forEach(line => line.classList.remove('hidden'));
            updateVisibleLines(); updateSearch();
        }
        function updateVisibleLines() {
            visibleLines = Array.from(document.querySelectorAll('.log-line:not(.hidden)'));
            allLines = Array.from(document.querySelectorAll('.log-line'));
        }
        function highlightSearch() {
            const filter = document.getElementById('searchInput').value.toLowerCase();
            let matchCount = 0;
            allLines.forEach(line => line.classList.remove('highlight'));
            if (filter === '') {
                currentMatchIndex = -1;
                document.getElementById('match-counter').innerText = '0/0';
                document.getElementById('matchIndex').value = ''; document.getElementById('matchIndex').max = 0;
                return;
            }
            visibleLines.forEach(line => {
                if (line.textContent.toLowerCase().includes(filter)) { line.classList.add('highlight'); matchCount++; }
            });
            const mi = document.getElementById('matchIndex');
            if (matchCount > 0) {
                currentMatchIndex = 0;
                document.getElementById('match-counter').innerText = (currentMatchIndex+1)+'/'+matchCount;
                mi.max = matchCount; mi.value = currentMatchIndex + 1;
                const fm = document.querySelectorAll('.log-line.highlight')[0];
                if (fm) fm.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                currentMatchIndex = -1;
                document.getElementById('match-counter').innerText = '0/0';
                mi.value = ''; mi.max = 0;
            }
        }
        function navigate(direction) {
            const matches = document.querySelectorAll('.log-line.highlight');
            if (matches.length === 0) return;
            currentMatchIndex = direction === 'prev'
                ? (currentMatchIndex - 1 + matches.length) % matches.length
                : (currentMatchIndex + 1) % matches.length;
            matches[currentMatchIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
            document.getElementById('match-counter').innerText = (currentMatchIndex+1)+'/'+matches.length;
            document.getElementById('matchIndex').value = currentMatchIndex + 1;
        }
        function gotoMatch() {
            const input = document.getElementById('matchIndex');
            const idx = parseInt(input.value, 10);
            const matches = document.querySelectorAll('.log-line.highlight');
            if (matches.length === 0) return;
            if (isNaN(idx) || idx < 1 || idx > matches.length) return;
            currentMatchIndex = idx - 1;
            matches[currentMatchIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
            document.getElementById('match-counter').innerText = (currentMatchIndex+1)+'/'+matches.length;
            input.value = currentMatchIndex + 1;
        }
        let autoRefreshTimer = null;
        function startAutoRefresh() {
            const btn = document.getElementById('autoRefreshBtn');
            if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; btn.textContent = '自动刷新: 关'; return; }
            autoRefreshTimer = setInterval(() => { updateVisibleLines(); if (document.getElementById('searchInput').value) highlightSearch(); }, 3000);
            btn.textContent = '自动刷新: 开';
        }
        document.addEventListener('DOMContentLoaded', function() {
            updateVisibleLines();
            document.getElementById('searchInput').addEventListener('input', highlightSearch);
            document.getElementById('prevMatch').addEventListener('click', () => navigate('prev'));
            document.getElementById('nextMatch').addEventListener('click', () => navigate('next'));
            document.getElementById('gotoMatch').addEventListener('click', gotoMatch);
            document.getElementById('matchIndex').addEventListener('keypress', function(e) { if (e.key === 'Enter') gotoMatch(); });
            document.getElementById('applyTimeRange').addEventListener('click', filterByTimeRange);
            document.getElementById('clearTimeRange').addEventListener('click', clearTimeRange);
            document.getElementById('refreshBtn').addEventListener('click', () => location.reload());
            document.getElementById('autoRefreshBtn').addEventListener('click', startAutoRefresh);
        });
"""

CSS_CLASS_MAP = {
    "system_joinleave": "system-joinleave",
    "system_death": "system-death",
    "system_other": "system-other",
    "user_normal": "user-normal",
    "user_atbot": "user-atbot",
    "robot_reply": "robot-reply",
    "robot_comment": "robot-comment",
    "separator": "separator",
    "raw": "",
    "normal": "",
}


def _html_head(title="Minecraft 聊天日志"):
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
{HTML_STYLE}
    </style>
</head>
<body>
    <div id="search-container">
        <input type="text" id="searchInput" placeholder="搜索关键词...">
        <div id="search-nav">
            <button id="prevMatch">↑</button>
            <button id="nextMatch">↓</button>
        </div>
        <span id="match-counter">0/0</span>
        <div id="jump-to">
            <input type="number" id="matchIndex" min="1" step="1">
            <button id="gotoMatch">跳转</button>
        </div>
        <div id="time-range">
            <input type="text" id="startTime" placeholder="开始时间 (如 2026.3.15/08:00)">
            <input type="text" id="endTime" placeholder="结束时间 (如 2026.3.15/20:00)">
            <button id="applyTimeRange">应用时间范围</button>
            <button id="clearTimeRange">清除</button>
        </div>
        <button id="refreshBtn">刷新页面</button>
        <button id="autoRefreshBtn">自动刷新: 关</button>
    </div>
    <script>
{HTML_SCRIPT}
    </script>
<div class="separator">====================================================</div>
"""


def _line_html(line: str, msg_type: str, ts_sec: float) -> str:
    safe_line = _html.escape(line)
    return f'<div class="log-line" data-timestamp="{ts_sec}">{safe_line}</div>'


class ChatLogger:
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._total_txt = self.log_dir / "chat_log.txt"
        self._total_html = self.log_dir / "chat_log.html"
        self._txt_dir = self.log_dir / "txt"
        self._html_dir = self.log_dir / "html"

        self._total_fh = open(str(self._total_txt), "a", encoding="utf-8")
        self._flush_counter = 0
        self._total_count = 0
        self._ring_buffer: deque[dict] = deque(maxlen=RING_BUFFER_SIZE)

    # ---------- 运行时写入（仅总 TXT + 环形缓存）----------

    def write(self, line: str, msg_type: str = "normal") -> None:
        """写入一行到总 TXT 文件和内存环形缓存。不生成 HTML。"""
        self._total_fh.write(line + "\n")
        self._flush_counter += 1
        self._total_count += 1
        if self._flush_counter >= 1:
            self._total_fh.flush()
            self._flush_counter = 0

        ts_match = re.match(r'^(\[\d+\.\d+\.\d+/\d+:\d+\])', line)
        ts_sec = timestamp_to_seconds(ts_match.group(1)) if ts_match else _time.time()

        self._ring_buffer.append({
            "ts": ts_sec,
            "line": line,
            "type": msg_type,
        })

    def flush(self) -> None:
        if self._total_fh:
            self._total_fh.flush()
        self._flush_counter = 0

    def close(self) -> None:
        self.flush()
        if self._total_fh:
            self._total_fh.close()
            self._total_fh = None

    def get_recent_messages(self, since_ts: float = 0) -> list[dict]:
        return [m for m in self._ring_buffer if m["ts"] > since_ts]

    @property
    def total_count(self) -> int:
        return self._total_count

    # ---------- 同步：从总 TXT 重建所有 HTML 和按天文件 ----------

    def sync(self) -> dict:
        """从总 TXT 读取全部行，重建：
        - 总 HTML（logs/chat_log.html）
        - 按天 TXT（logs/txt/chat_log_YYYY-MM-DD.txt）
        - 按天 HTML（logs/html/chat_log_YYYY-MM-DD.html）

        返回统计信息 dict。
        """
        self.flush()

        if not self._total_txt.exists():
            return {"total_lines": 0, "days": []}

        # 按天分组
        day_entries: dict[str, list[tuple[str, str, float]]] = {}
        total_lines = 0

        with open(str(self._total_txt), "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                if not line:
                    continue
                total_lines += 1

                ts_match = re.match(r'^(\[(\d+)\.(\d+)\.(\d+)/\d+:\d+\])', line)
                if ts_match:
                    ts_sec = timestamp_to_seconds(ts_match.group(1))
                    date_key = f"{int(ts_match.group(2)):04d}-{int(ts_match.group(3)):02d}-{int(ts_match.group(4)):02d}"
                else:
                    ts_sec = 0
                    continue  # 跳过无时间戳的行（分隔符等）

                msg_type = _classify_line(line)
                day_entries.setdefault(date_key, []).append((line, msg_type, ts_sec))

        # 确保目录存在
        self._txt_dir.mkdir(parents=True, exist_ok=True)
        self._html_dir.mkdir(parents=True, exist_ok=True)

        # 写总 HTML
        with open(str(self._total_html), "w", encoding="utf-8") as f:
            f.write(_html_head("Minecraft 聊天日志（总览）"))
            for date_key in sorted(day_entries):
                for line, msg_type, ts_sec in day_entries[date_key]:
                    div = _line_html(line, msg_type, ts_sec)
                    f.write(div + "\n")
            f.write("</body>\n</html>")

        # 写按天文件
        day_names = []
        for date_key in sorted(day_entries):
            entries = day_entries[date_key]
            day_names.append(date_key)

            # TXT
            txt_path = self._txt_dir / f"chat_log_{date_key}.txt"
            with open(str(txt_path), "w", encoding="utf-8") as f:
                for line, _, _ in entries:
                    f.write(line + "\n")

            # HTML
            html_path = self._html_dir / f"chat_log_{date_key}.html"
            with open(str(html_path), "w", encoding="utf-8") as f:
                f.write(_html_head(f"聊天日志 {date_key}"))
                for line, msg_type, ts_sec in entries:
                    div = _line_html(line, msg_type, ts_sec)
                    f.write(div + "\n")
                f.write("</body>\n</html>")

        return {"total_lines": total_lines, "days": day_names,
                "total_html": str(self._total_html),
                "txt_dir": str(self._txt_dir),
                "html_dir": str(self._html_dir)}


def _classify_line(line: str) -> str:
    """根据行内容推断 msg_type（用于从纯 TXT 重建 HTML 时着色）。"""
    if line.startswith("[") and "]" in line:
        _, rest = line.split("]", 1)
        rest = rest.strip()
    else:
        rest = line

    if rest.startswith("[机器人]") or rest.startswith("* "):
        return "robot_comment"
    lower = rest.lower()
    if any(kw in lower for kw in ["joined the game", "left the game"]):
        return "system_joinleave"
    if any(kw in lower for kw in [
        "was slain", "fell out of the world", "fell from a high place",
        "was killed", "slain", "died",
    ]):
        return "system_death"
    system_kw = [
        "joined the game", "left the game", "was slain", "fell out of the world",
        "fell from a high place", "was killed", "by ", "slain", "died",
        "has made the advancement",
    ]
    if any(kw in lower for kw in system_kw):
        return "system_other"
    if ": @bot" in rest or rest.startswith("@bot"):
        return "user_atbot"
    return "user_normal"


# ========== 旧日志迁移 ==========

def parse_old_log_line(line: str):
    m = re.match(r'^(\[\d+\.\d+\.\d+/\d+:\d+\])\s*(.*)', line)
    if not m:
        return None, None, None
    timestamp = m.group(1)
    rest = m.group(2)

    if rest.startswith("[机器人]"):
        return timestamp, rest, "robot_comment"
    lower = rest.lower()
    if any(kw in lower for kw in ["joined the game", "left the game"]):
        return timestamp, rest, "system_joinleave"
    if any(kw in lower for kw in [
        "was slain", "fell out of the world", "fell from a high place",
        "was killed", "slain", "died",
    ]):
        return timestamp, rest, "system_death"
    system_kw = [
        "joined the game", "left the game", "was slain", "fell out of the world",
        "fell from a high place", "was killed", "by ", "slain", "died",
        "has made the advancement",
    ]
    if any(kw in lower for kw in system_kw):
        return timestamp, rest, "system_other"
    if ": @bot" in rest or rest.startswith("@bot"):
        return timestamp, rest, "user_atbot"
    return timestamp, rest, "user_normal"


def merge_old_log(old_log_file: str = "chat_log.txt", total_log_file: str = "chat_log.html"):
    if not os.path.exists(old_log_file):
        return
    print("[INFO] Found old log file chat_log.txt, merging...")
    entries = []
    with open(old_log_file, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line or line.startswith("=") or line.startswith("本次开始于") or line.startswith("本次退出于"):
                continue
            ts, content, msg_type = parse_old_log_line(line)
            if ts is None:
                continue
            ts_sec = timestamp_to_seconds(ts)
            safe_content = _html.escape(f"{ts} {content}")
            html_line = f'<div class="log-line" data-timestamp="{ts_sec}">{safe_content}</div>'
            entries.append((ts_sec, html_line))

    if os.path.exists(total_log_file):
        with open(total_log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if 'log-line' not in line or 'data-timestamp' not in line:
                    continue
                m = re.search(r'data-timestamp="([^"]+)"', line)
                if m:
                    entries.append((float(m.group(1)), line))

    entries.sort(key=lambda x: x[0])

    with open(total_log_file, "w", encoding="utf-8") as f:
        f.write(_html_head("Minecraft 聊天日志（总览）"))
        for _, html_line in entries:
            f.write(html_line + "\n")

    backup = old_log_file + ".bak"
    if os.path.exists(backup):
        os.remove(backup)
    shutil.move(old_log_file, backup)
    print(f"[OK] Old log merged, backup at {backup}")