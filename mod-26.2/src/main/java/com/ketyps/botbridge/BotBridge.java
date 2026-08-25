package com.ketyps.botbridge;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.minecraft.client.Minecraft;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.InetSocketAddress;

public class BotBridge implements ClientModInitializer {

    public static final String MOD_ID = "botbridge";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    private static BotBridgeServer server;
    private static BotBridgeConfig config;

    @Override
    public void onInitializeClient() {
        config = BotBridgeConfig.createAndLoad();

        if (!config.enabled()) {
            LOGGER.info("BotBridge 已在配置中禁用，不启动 WebSocket 服务器");
            return;
        }

        try {
            server = new BotBridgeServer(new InetSocketAddress(config.host(), config.port()));
            server.start();
        } catch (Exception e) {
            LOGGER.error("BotBridge WebSocket 服务器启动失败", e);
            return;
        }

        ClientReceiveMessageEvents.CHAT.register((message, signedMessage, sender, params, receptionTimestamp) -> {
            if (sender == null) return;
            String senderName = sender.getName();
            String content = message.getString();
            server.broadcastChat(senderName, content);
        });

        ClientReceiveMessageEvents.GAME.register((message, overlay) -> {
            if (overlay) return;
            server.broadcastGame(message.getString());
        });

        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> {
            if (server != null) {
                try {
                    server.stop();
                } catch (InterruptedException e) {
                    LOGGER.error("BotBridge 服务器停止时出错", e);
                }
            }
        });

        LOGGER.info("BotBridge 已初始化，监听 ws://{}:{}", config.host(), config.port());
    }

    /**
     * 读取本地玩家(当前客户端账号)的名字,用于身份握手。
     * 未进游戏时返回 null;可能从 WebSocket 线程调用,仅做只读访问。
     */
    static String getLocalPlayerName() {
        Minecraft client = Minecraft.getInstance();
        if (client != null && client.player != null) {
            return client.player.getName().getString();
        }
        return null;
    }

    static void submitToGame(String text) {
        Minecraft client = Minecraft.getInstance();
        // 聊天发送链路(签名消息、LastSeenMessageCollector、聊天历史、MessageLimiter)
        // 会读写客户端状态,必须在渲染线程执行;从 WebSocket 线程直接调用属于数据竞争。
        client.execute(() -> {
            try {
                if (client.player == null) {
                    LOGGER.warn("player 为空，无法发送消息: {}", text);
                    return;
                }
                if (client.player.connection == null) {
                    LOGGER.warn("connection 为空，无法发送消息: {}", text);
                    return;
                }
                if (text.startsWith("/")) {
                    String cmd = text.substring(1);
                    LOGGER.info("执行命令: /{}", cmd);
                    client.player.connection.sendCommand(cmd);
                    LOGGER.info("命令 /{} 已发出", cmd);
                } else {
                    LOGGER.info("发送聊天消息: {}", text);
                    client.player.connection.sendChat(text);
                }
            } catch (Exception e) {
                LOGGER.error("发送消息到游戏失败: {}", text, e);
            }
        });
    }
}
