package com.ketyps.botbridge;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.minecraft.client.MinecraftClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.InetSocketAddress;

public class BotBridge implements ModInitializer {

    public static final String MOD_ID = "botbridge";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    private static BotBridgeServer server;
    private static BotBridgeConfig config;

    @Override
    public void onInitialize() {
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

    static void submitToGame(String text) {
        LOGGER.info("submitToGame 收到消息: {}", text);
        // 跟旧 chatsocket 一样，直接从 WebSocket 线程调用 sendCommand
        // 不需要 client.execute()，Netty 的 Channel 是线程安全的
        try {
            MinecraftClient client = MinecraftClient.getInstance();
            if (client.player == null) {
                LOGGER.warn("player 为空，无法发送消息: {}", text);
                return;
            }
            if (client.player.networkHandler == null) {
                LOGGER.warn("networkHandler 为空，无法发送消息: {}", text);
                return;
            }
            if (text.startsWith("/")) {
                String cmd = text.substring(1);
                LOGGER.info("执行命令: /{}", cmd);
                // 用 sendChatCommand 而不是 sendCommand——旧 chatsocket 用的这个
                client.player.networkHandler.sendChatCommand(cmd);
                LOGGER.info("命令 /{} 已发出", cmd);
            } else {
                LOGGER.info("发送聊天消息: {}", text);
                client.player.networkHandler.sendChatMessage(text);
            }
        } catch (Exception e) {
            LOGGER.error("发送消息到游戏失败: {}", text, e);
        }
    }
}
