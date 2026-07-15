# BotBridge

给 ketyps 的 Minecraft AI bot 项目用的最小聊天桥接 mod。不依赖 owo，协议直接对齐现有
Python 端（`sender_patterns` / `send_mode`），接入时 Python 侧代码不需要改。

## 这是什么

一个 Fabric **客户端** mod：
- 监听聊天/系统消息，转发成纯文本行 `<玩家名> 内容` / `[系统] 内容`
- 内嵌一个 WebSocket 服务器（默认 `ws://127.0.0.1:8080`），bot 作为 WS 客户端连上来
- 收到 bot 发来的纯文本，`/` 开头当指令执行，否则当普通聊天发送 —— 不需要 JSON 包装

## 跟 chatsocket 的区别

- 不依赖 owo，只依赖 Fabric API，没有版本联动的烦恼
- 入站消息不强制 JSON 解析，跟现有 `utils.py` 的 `raw`/`me`/`say` 模式直接兼容，不用切
  `send_mode` 为 json

## 编译前需要做的事（我没法在这边验证，你需要自己核对）

1. 用 [Fabric 官方模板](https://github.com/FabricMC/fabric-example-mod) 起一个新项目，
   或者把这几个文件放进模板对应位置替换：
   - `src/main/java/com/ketyps/botbridge/*.java`
   - `src/main/resources/fabric.mod.json`
   - `build.gradle`
   - `gradle.properties`
2. 去 https://fabricmc.net/develop/ 查一下 MC 1.21.5 对应的 **准确** `yarn_mappings` /
   `loader_version` / `fabric_version`，填进 `gradle.properties`（我写的是格式示例，
   不保证是当前实际可用的具体 build 号）。
3. `./gradlew build`，产物在 `build/libs/botbridge-0.1.0.jar`。
4. 装进 Fabric 客户端的 `mods` 目录，只需要额外装 **Fabric API**，不需要 owo。

## Python 端怎么接

实例配置里 `ws_url` 改成 `ws://127.0.0.1:8080`（跟默认配置一致的话甚至不用改），
`sender_patterns`、`send_mode` 保持现在的设置即可，不需要额外适配。

## 已知的简化/待办

- 配置目前只有 `host`/`port`/`enabled` 三项，改端口需要手动编辑
  `.minecraft/config/botbridge.json` 后重启客户端。
- 没有做 `system_msg_prefix` / `skip_msg_prefix` 之外消息类型的精细过滤，如果发现
  某类系统消息不该转发（比如成就提示），需要在 `BotBridge.java` 的 GAME 监听里加判断。
- 没有做连接鉴权，任何能连到这个端口的人都能读聊天、发消息，仅建议本地回环使用。
