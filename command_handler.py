# Refactor: 泛用性改造
import json
from dataclasses import dataclass, field
from pathlib import Path

from utils import clean_for_minecraft, make_safe_say, make_safe_me, build_command


@dataclass
class CommandEntry:
    name: str
    aliases: list[str]
    description: str
    response: str
    mode: str       # "say" or "me"
    admin_only: bool
    action: str = ""


@dataclass
class CommandHandler:
    commands_file: Path
    max_command_bytes: int = 500
    _commands: dict[str, CommandEntry] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.commands_file, str):
            self.commands_file = Path(self.commands_file)
        self._commands, _ = self._load_from_file()

    def _load_from_file(self) -> tuple[dict[str, CommandEntry], bool]:
        """加载指令文件，返回 (指令表, 是否解析成功)。

        解析成功包含合法的空指令数组（此时指令表为空字典），
        解析失败则指令表为空字典但第二个元素为 False。
        """
        if not self.commands_file.exists():
            print(f"[WARN] Commands file not found: {self.commands_file}")
            return {}, False

        try:
            data = json.loads(self.commands_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[WARN] Commands JSON parse error: {e}")
            return {}, False

        if not isinstance(data, dict) or "commands" not in data:
            print("[WARN] Commands JSON missing 'commands' array")
            return {}, False

        commands: dict[str, CommandEntry] = {}
        seen_names: set[str] = set()
        for item in data["commands"]:
            name = item.get("name", "").strip().lower()
            if not name:
                continue
            if name in seen_names:
                print(f"[WARN] Duplicate command name: '{name}', last wins")
            seen_names.add(name)

            commands[name] = CommandEntry(
                name=name,
                aliases=[a.strip().lower() for a in item.get("aliases", []) if a.strip()],
                description=item.get("description", ""),
                response=item.get("response", ""),
                mode=item.get("mode", "me"),
                admin_only=item.get("admin_only", False),
                action=item.get("action", ""),
            )

        # 同时将别名映射到同一个 entry
        for cmd in list(commands.values()):
            for alias in cmd.aliases:
                if alias in commands:
                    print(f"[WARN] Alias '{alias}' conflicts with command name, skipped")
                else:
                    commands[alias] = cmd

        if seen_names:
            print(f"[OK] Loaded {len(seen_names)} custom commands")
        return commands, True

    def _count_unique(self) -> int:
        """返回去重后的指令名数量（不含别名）。"""
        return sum(1 for k, v in self._commands.items() if k == v.name)

    def reload(self) -> tuple[bool, int]:
        """重新加载指令文件。

        返回 (是否成功替换, 当前唯一指令数量)。
        解析失败且原表非空时会保留旧表，不会清空。
        """
        new_commands, ok = self._load_from_file()
        if ok:
            self._commands = new_commands
            count = self._count_unique()
            print(f"[OK] Custom commands reloaded ({count} unique)")
            return True, count
        else:
            # 解析失败：保留旧表
            count = self._count_unique()
            if count > 0:
                print(f"[WARN] Reload failed, keeping {count} old commands")
            else:
                print("[WARN] Reload failed, no commands loaded")
            return False, count

    def match(self, user_message: str) -> CommandEntry | None:
        key = user_message.strip().lower()
        return self._commands.get(key)

    def format_response(self, entry: CommandEntry) -> str:
        safe_text = clean_for_minecraft(entry.response)
        if entry.mode == "raw":
            return build_command(safe_text, self.max_command_bytes, mode="raw")
        if entry.mode == "say":
            return make_safe_say(safe_text, self.max_command_bytes)
        return make_safe_me(safe_text, self.max_command_bytes)
