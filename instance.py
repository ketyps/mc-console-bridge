# Refactor: 完整 raw_msg 透传 + Fixed: BUG-B, BUG-C, 泛用性改造
"""BotInstance — 每一个 Minecraft 服务器实例对应一个独立文件夹。
文件夹结构:
    instances/<name>/
        .env                  # API Key、WS URL、Bot Name 等
        system_prompt.txt     # 系统提示词
        auto_comment_prompt.txt
        custom_commands.json  # 自定义指令
"""

import json
import re
import shutil
from pathlib import Path
from dataclasses import dataclass, field

from config import get_data_root, get_resource_root, load_text_file


# ========== 实例文件夹内的文件名常量 ==========
ENV_FILE = ".env"
SYSTEM_PROMPT_FILE = "system_prompt.txt"
AUTO_COMMENT_PROMPT_FILE = "auto_comment_prompt.txt"
COMMANDS_FILE = "custom_commands.json"

INSTANCES_DIR_NAME = "instances"


def _parse_dotenv(path: Path) -> dict[str, str]:
    """手动解析 .env 文件，返回 key-value 字典（含空值）。"""
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _validate_name(name: str) -> None:
    if not name or not re.match(r'^[a-zA-Z0-9_\-一-鿿]+$', name):
        raise ValueError(
            f"实例名称 '{name}' 不合法，只允许字母、数字、下划线、连字符和中文字符"
        )


def _normalize_relpath(p: str) -> str:
    """如果路径是绝对路径，只取最后一级目录名（保障发布版便携性）。"""
    pp = Path(p)
    return pp.name if pp.is_absolute() else p


@dataclass
class BotInstance:
    name: str
    folder: Path

    # ---------- .env 字段 ----------
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    model_pro: str = "deepseek-v4-pro"
    model_flash: str = "deepseek-v4-flash"
    ws_url: str = "ws://127.0.0.1:8080"
    bot_name: str = ""
    admin_username: str = ""
    sender_patterns: str = "<{name}>,{name}:"

    @property
    def admin_list(self) -> list[str]:
        """将逗号分隔的管理员字符串拆分为列表。"""
        return [a.strip() for a in self.admin_username.split(",") if a.strip()]

    # ---------- 提示词 ----------
    system_prompt: str = ""
    auto_comment_prompt: str = ""

    # ---------- 运作参数 ----------
    trigger_prefix: str = "@bot"
    send_mode: str = "me"
    cooldown_seconds: int = 15
    reply_prefix: str = ""
    comment_prefix: str = "[氛围感知] "
    system_msg_prefix: str = ""
    skip_msg_prefix: str = ""

    # ---------- JSON 数据 ----------
    custom_commands: list[dict] = field(default_factory=list)

    # ---------- 日志 ----------
    log_dir: str = "logs"

    # ---------- 调优参数 ----------
    max_history: int = 20
    global_context_size: int = 10
    max_command_bytes: int = 500
    auto_comment_interval: int = 300
    heartbeat_check_interval: int = 30
    heartbeat_timeout: int = 600
    api_timeout: int = 15
    temperature: float = 0.7
    max_tokens: int = 300
    retry_count: int = 2
    retry_delay: float = 1.5
    reconnect_delay: int = 5
    reconnect_delay_long: int = 10

    # ========== 工厂方法 ==========

    @classmethod
    def load(cls, name: str, base_dir: Path | None = None) -> "BotInstance":
        """从 instances/<name>/ 加载实例。如果 base_dir 为 None，使用项目根目录。"""
        _validate_name(name)
        if base_dir is None:
            base_dir = get_data_root()
        folder = base_dir / INSTANCES_DIR_NAME / name

        if not folder.exists():
            raise InstanceLoadError(f"实例文件夹不存在: {folder}")

        env_path = folder / ENV_FILE
        if not env_path.exists():
            raise InstanceLoadError(f"实例缺少 .env 文件: {env_path}")

        # 加载 .env（手动解析，不修改全局环境变量）
        env = _parse_dotenv(env_path)

        api_key = env.get("DEEPSEEK_API_KEY", "")

        def _str(key: str, default: str, allow_empty: bool = False) -> str:
            """读取字符串，allow_empty=True 时允许空值，否则空值回退默认。"""
            v = env.get(key)
            if v is None:
                return default
            if not allow_empty and v == "":
                return default
            return v

        def _num(key: str, default, cast):
            """读取数字，字段不存在或为空时回退默认。"""
            v = env.get(key)
            if v is None or v == "":
                return default
            try:
                return cast(v)
            except (ValueError, TypeError) as e:
                # [FIX-P0-4] cast 失败时打印具体字段名和原始值，方便定位是哪个 .env 配置项写错了
                print(f"[WARN] 配置项 {key}='{v}' 转换失败（{e}），已回退默认值 {default}")
                return default

        instance = cls(
            name=name,
            folder=folder,
            deepseek_api_key=api_key,
            deepseek_api_url=_str("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"),
            model_pro=_str("MODEL_PRO", "deepseek-v4-pro"),
            model_flash=_str("MODEL_FLASH", "deepseek-v4-flash"),
            ws_url=_str("WS_URL", "ws://127.0.0.1:8080"),
            bot_name=_str("BOT_NAME", "", allow_empty=True),
            admin_username=_str("ADMIN_USERNAME", "", allow_empty=True),
            sender_patterns=_str("SENDER_PATTERNS", "<{name}>,{name}:", allow_empty=False),
            trigger_prefix=_str("TRIGGER_PREFIX", "@bot"),
            send_mode=_str("SEND_MODE", "me"),
            cooldown_seconds=_num("COOLDOWN_SECONDS", 15, int),
            reply_prefix=_str("REPLY_PREFIX", "", allow_empty=True),
            comment_prefix=_str("COMMENT_PREFIX", "[氛围感知] ", allow_empty=True),
            system_msg_prefix=_str("SYSTEM_MSG_PREFIX", "", allow_empty=True),
            skip_msg_prefix=_str("SKIP_MSG_PREFIX", "", allow_empty=True),
            # 日志（归一化为相对路径，确保便携性）
            log_dir=_normalize_relpath(_str("LOG_DIR", "logs")),
            # 提示词
            system_prompt=load_text_file(folder / SYSTEM_PROMPT_FILE),
            auto_comment_prompt=load_text_file(folder / AUTO_COMMENT_PROMPT_FILE),
            # 调优参数
            max_history=_num("MAX_HISTORY", 20, int),
            global_context_size=_num("GLOBAL_CONTEXT_SIZE", 10, int),
            max_command_bytes=_num("MAX_COMMAND_BYTES", 500, int),
            auto_comment_interval=_num("AUTO_COMMENT_INTERVAL", 300, int),
            heartbeat_check_interval=_num("HEARTBEAT_CHECK_INTERVAL", 30, int),
            heartbeat_timeout=_num("HEARTBEAT_TIMEOUT", 600, int),
            api_timeout=_num("API_TIMEOUT", 15, int),
            temperature=_num("TEMPERATURE", 0.7, float),
            max_tokens=_num("MAX_TOKENS", 300, int),
            retry_count=_num("RETRY_COUNT", 2, int),
            retry_delay=_num("RETRY_DELAY", 1.5, float),
            reconnect_delay=_num("RECONNECT_DELAY", 5, int),
            reconnect_delay_long=_num("RECONNECT_DELAY_LONG", 10, int),
        )

        # 加载自定义指令
        commands_path = folder / COMMANDS_FILE
        if commands_path.exists():
            try:
                data = json.loads(commands_path.read_text(encoding="utf-8"))
                instance.custom_commands = data.get("commands", [])
            except (json.JSONDecodeError, OSError):
                instance.custom_commands = []

        return instance

    # ========== 保存方法 ==========

    def save_env(self) -> None:
        """将当前配置写回 .env 文件。"""
        # 发布包便携性：LOG_DIR 必须存相对路径，避免开发机绝对路径泄漏
        log_dir = self.log_dir
        if Path(log_dir).is_absolute():
            log_dir = Path(log_dir).name
        lines = [
            f"DEEPSEEK_API_KEY={self.deepseek_api_key}",
            f"DEEPSEEK_API_URL={self.deepseek_api_url}",
            f"MODEL_PRO={self.model_pro}",
            f"MODEL_FLASH={self.model_flash}",
            f"WS_URL={self.ws_url}",
            f"BOT_NAME={self.bot_name}",
            f"ADMIN_USERNAME={self.admin_username}",
            f"SENDER_PATTERNS={self.sender_patterns}",
            f"TRIGGER_PREFIX={self.trigger_prefix}",
            f"SEND_MODE={self.send_mode}",
            f"COOLDOWN_SECONDS={self.cooldown_seconds}",
            f"REPLY_PREFIX={self.reply_prefix}",
            f"COMMENT_PREFIX={self.comment_prefix}",
            f"SYSTEM_MSG_PREFIX={self.system_msg_prefix}",
            f"SKIP_MSG_PREFIX={self.skip_msg_prefix}",
            f"LOG_DIR={log_dir}",
            f"MAX_HISTORY={self.max_history}",
            f"GLOBAL_CONTEXT_SIZE={self.global_context_size}",
            f"MAX_COMMAND_BYTES={self.max_command_bytes}",
            f"AUTO_COMMENT_INTERVAL={self.auto_comment_interval}",
            f"HEARTBEAT_CHECK_INTERVAL={self.heartbeat_check_interval}",
            f"HEARTBEAT_TIMEOUT={self.heartbeat_timeout}",
            f"API_TIMEOUT={self.api_timeout}",
            f"TEMPERATURE={self.temperature}",
            f"MAX_TOKENS={self.max_tokens}",
            f"RETRY_COUNT={self.retry_count}",
            f"RETRY_DELAY={self.retry_delay}",
            f"RECONNECT_DELAY={self.reconnect_delay}",
            f"RECONNECT_DELAY_LONG={self.reconnect_delay_long}",
            "",
        ]
        (self.folder / ENV_FILE).write_text("\n".join(lines), encoding="utf-8")

    def save_prompts(self) -> None:
        """保存提示词文件。"""
        (self.folder / SYSTEM_PROMPT_FILE).write_text(self.system_prompt, encoding="utf-8")
        (self.folder / AUTO_COMMENT_PROMPT_FILE).write_text(self.auto_comment_prompt, encoding="utf-8")

    def save_commands(self) -> None:
        """保存自定义指令 JSON。"""
        data = {"commands": self.custom_commands}
        (self.folder / COMMANDS_FILE).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ========== 实例管理 ==========

    @classmethod
    def list_instances(cls, base_dir: Path | None = None) -> list[str]:
        """列出所有可用实例名称。"""
        if base_dir is None:
            base_dir = get_data_root()
        instances_dir = base_dir / INSTANCES_DIR_NAME
        if not instances_dir.exists():
            return []
        return sorted(
            d.name for d in instances_dir.iterdir()
            if d.is_dir() and (d / ENV_FILE).exists()
        )

    @classmethod
    def create(cls, name: str, base_dir: Path | None = None,
               template: "BotInstance | None" = None) -> "BotInstance":
        """新建实例文件夹。如果提供 template，从模板复制文件。"""
        _validate_name(name)
        if base_dir is None:
            base_dir = get_data_root()
        folder = base_dir / INSTANCES_DIR_NAME / name
        folder.mkdir(parents=True, exist_ok=True)

        if template:
            # 复制模板的所有配置文件
            for fname in [ENV_FILE, SYSTEM_PROMPT_FILE, AUTO_COMMENT_PROMPT_FILE,
                          COMMANDS_FILE]:
                src = template.folder / fname
                if src.exists():
                    shutil.copy2(src, folder / fname)
            return cls.load(name, base_dir)
        else:
            # 创建空白实例（最小配置）
            env = folder / ENV_FILE
            env.write_text(
                "DEEPSEEK_API_KEY=\n"
                "DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions\n"
                "MODEL_PRO=deepseek-v4-pro\n"
                "MODEL_FLASH=deepseek-v4-flash\n"
                "WS_URL=ws://127.0.0.1:8080\n"
                "BOT_NAME=\n"
                "ADMIN_USERNAME=\n"
                "SENDER_PATTERNS=<{name}>,{name}:\n"
                "TRIGGER_PREFIX=@bot\n"
                "SEND_MODE=me\n"
                "COOLDOWN_SECONDS=15\n",
                encoding="utf-8",
            )
            (folder / SYSTEM_PROMPT_FILE).write_text(
                "你是 Minecraft 服务器里的一个 AI 玩家，性格友好活泼。\n"
                "你会收到服务器聊天栏里的完整消息，格式因服务器而异，可能是 <玩家名> 内容、玩家名: 内容 等。\n"
                "有人会在消息里 @你（使用触发词），你需要根据完整消息判断是谁在问什么，然后自然地回应。\n"
                "回复要求：\n"
                "- 像真正的玩家一样聊天，简短自然，不要书面化\n"
                "- 根据消息内容判断语气，不要无视上下文\n"
                "- 不要透露你是 AI\n"
                "- 不了解的事情就说不知道，不要编造\n"
                "- 单次回复控制在 3 句话以内",
                encoding="utf-8",
            )
            (folder / AUTO_COMMENT_PROMPT_FILE).write_text(
                "你是一个 Minecraft 服务器中的玩家，正在看聊天栏。\n"
                "请根据最近的聊天内容，发一条简短的评论，像路人插话一样自然。\n"
                "要求：语气随意活泼，一两句话即可，不要提及具体玩家名字。",
                encoding="utf-8",
            )
            (folder / COMMANDS_FILE).write_text(
                json.dumps({
                    "commands": [
                        {
                            "name": "帮助",
                            "response": "@bot 提问 即可向我提问！内置指令: switch pro / flash 切换模型, model 查看当前模型。",
                            "admin_only": False,
                        },
                        {
                            "name": "介绍",
                            "response": "我是服务器里的 AI 助手，可以聊天、答疑。叫我名字就能唤醒我~",
                            "admin_only": False,
                        },
                        {
                            "name": "switch pro",
                            "action": "switch_pro",
                            "description": "切换到高性能模型",
                            "admin_only": False,
                        },
                        {
                            "name": "switch flash",
                            "action": "switch_flash",
                            "description": "切换到快速模型",
                            "admin_only": False,
                        },
                        {
                            "name": "model",
                            "action": "show_model",
                            "description": "查看当前模型",
                            "admin_only": False,
                        },
                        {
                            "name": "reloadjson",
                            "action": "reload_commands",
                            "admin_only": True,
                        },
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return cls.load(name, base_dir)

    @classmethod
    def _get_folder(cls, name: str, base_dir: Path | None = None) -> Path:
        if base_dir is None:
            base_dir = get_data_root()
        return base_dir / INSTANCES_DIR_NAME / name

    def delete(self) -> None:
        """删除本实例文件夹。"""
        if self.folder.exists():
            shutil.rmtree(self.folder)

    def rename(self, new_name: str, base_dir: Path | None = None) -> "BotInstance":
        """重命名实例文件夹。"""
        _validate_name(new_name)  # [FIX-P0-3] 校验新名称合法性
        if base_dir is None:
            base_dir = get_data_root()
        new_folder = base_dir / INSTANCES_DIR_NAME / new_name
        if new_folder.exists():  # [FIX-P0-3] 检查目标文件夹是否已存在
            raise ValueError(f"目标实例 '{new_name}' 已存在")
        self.folder.rename(new_folder)
        self.name = new_name
        self.folder = new_folder
        return self

    def duplicate(self, new_name: str, base_dir: Path | None = None) -> "BotInstance":
        """复制本实例到新名称。"""
        return BotInstance.create(new_name, base_dir, template=self)


class InstanceLoadError(Exception):
    """实例加载失败。"""
    pass