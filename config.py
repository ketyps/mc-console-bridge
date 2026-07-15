# Fixed: BUG-8
"""轻量工具函数。路径辅助：区分只读资源和可写数据。"""
import sys
from pathlib import Path


def get_resource_root() -> Path:
    """只读资源根目录。
    开发环境: 项目根目录
    PyInstaller 打包后: sys._MEIPASS（临时解压目录，只读）
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def get_data_root() -> Path:
    """可写数据根目录（实例、日志、运行时配置）。
    开发环境: 项目根目录
    PyInstaller 打包后: exe 所在目录
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# 向后兼容
BASE_DIR = get_resource_root()

# 旧代码里 BASE_DIR 同时用于读取资源和写入数据；
# 新代码：读取用 BASE_DIR / get_resource_root()，写入用 get_data_root()


def load_text_file(path: Path) -> str:
    """读取文本文件，不存在则返回空字符串。"""
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""

