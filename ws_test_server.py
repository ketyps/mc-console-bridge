# Fixed: BUG-A
"""轻量 WebSocket 聊天测试服务器 — 模拟 Minecraft 聊天中转。
启动后自动监听 ws://127.0.0.1:8080，在控制台输入消息来模拟玩家发言。

用法：
    python ws_test_server.py                  # 默认端口 8080
    python ws_test_server.py --port 2401      # 自定义端口
"""
import asyncio
import argparse
import json
import sys
import websockets
from websockets.asyncio.server import serve

PORT = 8080

# 模拟的玩家名，你可以修改
DEFAULT_PLAYER = "TestPlayer"
CONNECTED_CLIENTS: set = set()


async def handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    addr = websocket.remote_address
    print(f"[+] 客户端已连接: {addr}")
    try:
        async for message in websocket:
            # 显示 bot 发回来的消息
            text = message.strip()
            if text.startswith("{"):
                try:
                    data = json.loads(text)
                    content = data.get("body", {}).get("content", text)
                except (ValueError, KeyError):
                    content = text
            else:
                content = text

            if content.startswith("/me "):
                print(f"\033[36m[Bot 动作] {content[4:]}\033[0m")
            elif content.startswith("/say "):
                print(f"\033[36m[Bot 说话] {content[5:]}\033[0m")
            else:
                print(f"\033[36m[Bot] {content}\033[0m")
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] 客户端断开: {addr}")
    finally:
        CONNECTED_CLIENTS.discard(websocket)


async def console_input(port: int):
    """从控制台读取玩家消息并广播给所有连接的客户端。"""
    print(f"\033[90m{'─' * 50}\033[0m")
    print(f"WebSocket 测试服务器已启动 → \033[1;32mws://127.0.0.1:{port}\033[0m")
    print()
    print("输入格式：")
    print(f"  @bot 你好                 → 以 <{DEFAULT_PLAYER}> @bot 你好 发送")
    print(f"  {DEFAULT_PLAYER}: 123     → 自定义发送者格式")
    print(f"  /player Alice            → 切换默认玩家名（当前: {DEFAULT_PLAYER}）")
    print(f"  /bot 你好                 → 等价于 @bot 你好")
    print(f"  [Ctrl+C]                 → 退出")
    print(f"\033[90m{'─' * 50}\033[0m")
    print()

    current_player = DEFAULT_PLAYER

    loop = asyncio.get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except (EOFError, OSError):
            break

        line = line.strip()
        if not line:
            continue

        if line.startswith("/player "):
            current_player = line[8:].strip()
            if current_player:
                print(f"  当前玩家切换为: \033[1;33m{current_player}\033[0m")
            continue

        if line.startswith("/bot "):
            line = f"@bot {line[5:]}"

        # 构建聊天消息
        if line.startswith("<"):
            # 已经是 <PlayerName> 格式
            raw_msg = line
        else:
            raw_msg = f"<{current_player}> {line}"

        print(f"\033[32m→ {raw_msg}\033[0m")

        # 广播给所有连接的 bot 客户端
        dead = set()
        for ws in CONNECTED_CLIENTS:
            try:
                await ws.send(raw_msg)
            except websockets.exceptions.ConnectionClosed:
                dead.add(ws)
            except Exception as e:
                print(f"[!] 发送失败: {e}")
                dead.add(ws)
        CONNECTED_CLIENTS.difference_update(dead)

    print("\n\033[33m服务器已停止。\033[0m")


async def main():
    parser = argparse.ArgumentParser(description="MC WebSocket 测试服务器")
    parser.add_argument("--port", "-p", type=int, default=8080, help="监听端口")
    args = parser.parse_args()
    port = args.port

    print(f"\033[90m启动 WebSocket 服务器，端口 {port}...\033[0m")

    try:
        async with serve(handler, "127.0.0.1", port):
            await console_input(port)
    except OSError as e:
        print(f"\033[31m[FATAL] 无法绑定端口 {port}: {e}\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n\033[33m已退出。\033[0m")
