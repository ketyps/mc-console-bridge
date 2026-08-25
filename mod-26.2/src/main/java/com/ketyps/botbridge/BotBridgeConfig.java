package com.ketyps.botbridge;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonSyntaxException;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public class BotBridgeConfig {

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path CONFIG_PATH =
            FabricLoader.getInstance().getConfigDir().resolve("botbridge.json");

    private static class Data {
        String host = "127.0.0.1";
        int port = 8080;
        boolean enabled = true;
    }

    private final Data data;

    private BotBridgeConfig(Data data) {
        this.data = data;
    }

    public static BotBridgeConfig createAndLoad() {
        Data d = new Data();
        if (Files.exists(CONFIG_PATH)) {
            try {
                Data loaded = GSON.fromJson(Files.readString(CONFIG_PATH), Data.class);
                if (loaded != null) d = loaded;
            } catch (IOException | JsonSyntaxException e) {
                // 文件读不了或 JSON 语法错误时回退默认配置，而不是让 mod 初始化崩溃
                BotBridge.LOGGER.warn("BotBridge 配置解析失败，使用默认配置: {}", e.getMessage());
            }
        }
        BotBridgeConfig config = new BotBridgeConfig(d);
        config.save();
        return config;
    }

    private void save() {
        try {
            Files.createDirectories(CONFIG_PATH.getParent());
            Files.writeString(CONFIG_PATH, GSON.toJson(data));
        } catch (IOException e) {
            BotBridge.LOGGER.error("BotBridge 配置写入失败", e);
        }
    }

    public String host() { return data.host; }
    public int port() { return data.port; }
    public boolean enabled() { return data.enabled; }
}
