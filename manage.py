"""实例管理 CLI — 新建、删除、复制、列出、编辑实例。"""
import sys
from pathlib import Path
from instance import BotInstance


def cmd_list():
    names = BotInstance.list_instances()
    if not names:
        print("暂无实例，使用以下命令创建：")
        print("  python manage.py create <名称>")
        return
    print(f"共 {len(names)} 个实例：")
    for n in names:
        inst = BotInstance.load(n)
        print(f"  {n:20s}  bot={inst.bot_name:12s}  model={inst.model_flash}")


def cmd_create(name: str, template: str | None = None):
    if name in BotInstance.list_instances():
        print(f"实例 '{name}' 已存在。")
        return
    tmpl = None
    if template:
        tmpl = BotInstance.load(template)
    inst = BotInstance.create(name, template=tmpl)
    print(f"实例 '{name}' 已创建，配置文件在：")
    print(f"  {inst.folder}")
    print(f"下一步：编辑 {inst.folder / '.env'}，填入 API Key，然后运行：")
    print(f"  python main.py {name}")


def cmd_delete(name: str):
    names = BotInstance.list_instances()
    if name not in names:
        print(f"实例 '{name}' 不存在。可用实例：{', '.join(names) or '(无)'}")
        return
    inst = BotInstance.load(name)
    resp = input(f"确认删除实例 '{name}'（{inst.folder}）？[y/N] ")
    if resp.lower() == "y":
        inst.delete()
        print(f"已删除 '{name}'。")


def cmd_duplicate(source: str, target: str):
    names = BotInstance.list_instances()
    if source not in names:
        print(f"源实例 '{source}' 不存在。")
        return
    if target in names:
        print(f"目标名 '{target}' 已存在。")
        return
    inst = BotInstance.load(source)
    inst.duplicate(target)
    print(f"已从 '{source}' 复制到 '{target}'。")


def cmd_edit(name: str):
    names = BotInstance.list_instances()
    if name not in names:
        print(f"实例 '{name}' 不存在。")
        return
    inst = BotInstance.load(name)
    env_path = inst.folder / ".env"
    if sys.platform == "win32":
        import subprocess
        subprocess.run(["start", str(env_path)], shell=True)
    else:
        import os
        import subprocess
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(env_path)])


def main():
    if len(sys.argv) < 2:
        print("用法：")
        print("  python manage.py list                    列出全部实例")
        print("  python manage.py create <名称> [模板名]    新建实例（可选从模板复制）")
        print("  python manage.py delete <名称>            删除实例")
        print("  python manage.py copy <源> <新名称>        复制实例")
        print("  python manage.py edit <名称>              用编辑器打开 .env")
        print("")
        print("运行实例：")
        print("  python main.py <名称>")
        return

    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    elif cmd == "create":
        if len(sys.argv) < 3:
            print("用法: python manage.py create <名称> [模板名]")
            return
        cmd_create(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("用法: python manage.py delete <名称>")
            return
        cmd_delete(sys.argv[2])
    elif cmd == "copy":
        if len(sys.argv) < 4:
            print("用法: python manage.py copy <源> <新名称>")
            return
        cmd_duplicate(sys.argv[2], sys.argv[3])
    elif cmd == "edit":
        if len(sys.argv) < 3:
            print("用法: python manage.py edit <名称>")
            return
        cmd_edit(sys.argv[2])
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
