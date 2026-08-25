# BotBridge (MC 26.x / Mojang 映射版)

这是 BotBridge 针对 **Minecraft 26.x**(Mojang 改版后按年份命名的版本,如 26.2)的分叉构建。
与 `../mod/`(1.21.x,yarn 映射)并存,两者产出**不同且不通用**的 jar:

| 目录 | 目标 MC | 映射 | Java | jar |
|---|---|---|---|---|
| `mod/` | 1.21.5 ~ 1.21.x | yarn | 21 | `botbridge-0.2.2.jar` |
| `mod-26.2/` | 26.x | Mojang 官方映射(mojmap) | 25 | `botbridge-0.2.2-mc26.2.jar` |

## 关键配置(对照官方模板)

- `minecraft_version=26.2`、`loader_version=0.19.3`、`fabric_version=0.158.0+26.2`
- **`loom_version=1.17-SNAPSHOT`**、Gradle **9.5.1**(26.2 类文件是 Java 25,需 Gradle 9.x)
- **不用 yarn**(26.2 无 yarn),用 **Mojang 官方映射(mojmap)**
- 编译需 **JDK 25**(如 IntelliJ 自带 JBR: `D:\software\IntelliJ IDEA 2026.1.4\jbr`)

## 构建

```bash
set JAVA_HOME=D:\software\IntelliJ IDEA 2026.1.4\jbr
set Path=%JAVA_HOME%\bin;%Path%
gradlew build            # 产物 build/libs/botbridge-0.2.2-mc26.2.jar
```

## ⚠️ 当前状态

源码已按 mojmap 改写(`Minecraft`、`player.connection.sendCommand/sendChat` 等),配置与官方
`FabricMC/fabric-example-mod` 的 26.2 分支一致。**但 26.2 的构建映射目前可能尚未被当前可获取的
loom 稳定解析**(会出现 `Failed to find official mojang mappings for 26.2` 或
`Configuration 'mappings' has no dependencies`)。这属于 Fabric 26.2 工具链/映射未完全就绪,
不是本代码问题。待 loom/映射就绪后按上述命令构建即可。

生产环境请优先使用 `../mod/`(1.21.x)版本。
