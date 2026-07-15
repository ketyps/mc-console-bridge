"""独立子进程：弹出系统原生文件夹选择框，将选中路径打印到 stdout。"""
import tkinter as tk
from tkinter import filedialog
import sys

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
folder = filedialog.askdirectory(title="选择日志保存文件夹")
root.destroy()

# 输出选中路径到 stdout（如果用户取消则输出空行）
sys.stdout.write(folder or "")
sys.stdout.flush()
