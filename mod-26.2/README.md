# BotBridge (MC 26.x / Mojang 映射版)

BotBridge 针对 **Minecraft 26.x**(Mojang 改版后按年份命名的版本线,如 26.2)的分叉构建。
与 `../mod/`(1.21.x,yarn 映射)并存,两者产出**不同且不通用**的 jar:

| 目录 | 目标 MC | 映射 | Java | Gradle | jar |
|---|---|---|---|---|---|
| `mod/` | 1.21.5 ~ 1.21.x | yarn | 21 | 8.14 | `botbridge-0.2.2.jar` |
| `mod-26.2/` | 26.x | Mojang 官方映射(mojmap) | 25 | 9.7.1 | `botbridge-0.2.2-mc26.2.jar` |

## 26.x 的关键变化(踩坑记录)

1. **不再使用 yarn** —— 26.x 线改用 **Mojang 官方映射(mojmap)**,所以查不到 26.2 的 yarn 是正常的。
2. **运行时直接用 mojmap 名称**:1.21.x 的崩溃栈是 `net.minecraft.class_310`(intermediary),
   而 26.2 的是 `net.minecraft.client.Minecraft`(mojmap)。因此:
   - **没有 `remapJar` 任务**,`jar`/`build` 产出的就是可直接使用的生产 jar(无需再 remap);
   - 按 1.21.x(yarn/intermediary)编译的旧 jar **无法**在 26.x 运行(`NoClassDefFoundError: net/minecraft/class_XXX`)。
3. **插件 ID 必须写全名 `net.fabricmc.fabric-loom`**。
   用短名 `fabric-loom` 会导致 loom 不自动提供 26.x 映射,报
   `Configuration 'mappings' has no dependencies`。新版 loom 无需写 `mappings` 行。
4. **构建环境**:loom `1.18-SNAPSHOT`(当前 = 1.18.2)、Gradle **9.7.1**、**JDK 25**(26.2 类文件为 Java 25)。
5. **authlib 9.x 的 `GameProfile` 变成了 record**:取名字用 `sender.name()`,**不是** `getName()`。

## 构建(已验证通过)

```powershell
cd E:\bot\mc_ai_bot_modular\mod-26.2
$env:JAVA_HOME = "D:\software\IntelliJ IDEA 2026.1.4\jbr"   # 需 JDK 25
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat build --no-daemon
```

产物:`build/libs/botbridge-0.2.2-mc26.2.jar`(含内嵌 Java-WebSocket,可直接放入 `.minecraft/mods/`)

> 网络慢可挂代理:
> `$env:GRADLE_OPTS = "-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897"`

## 配置要点

- `minecraft_version=26.2`、`loader_version=0.19.3`、`fabric_version=0.158.0+26.2`
- `loom_version=1.18-SNAPSHOT`、Gradle wrapper `9.7.1`、`JavaVersion.VERSION_25`
- `fabric.mod.json` 依赖:`minecraft ">=26.0"`、`java ">=25"`、`fabric-api ">=0.149.2"`
