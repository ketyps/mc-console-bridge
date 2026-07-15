package com.ketyps.botbridge;

import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;

import java.net.InetSocketAddress;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class BotBridgeServer extends WebSocketServer {

    private final Set<WebSocket> clients = ConcurrentHashMap.newKeySet();

    public BotBridgeServer(InetSocketAddress address) {
        super(address);
    }

    @Override
    public void onOpen(WebSocket conn, ClientHandshake handshake) {
        clients.add(conn);
        BotBridge.LOGGER.info("bot 客户端已连接: {}", conn.getRemoteSocketAddress());
    }

    @Override
    public void onClose(WebSocket conn, int code, String reason, boolean remote) {
        clients.remove(conn);
        BotBridge.LOGGER.info("bot 客户端断开: {} (code={}, reason={})", conn.getRemoteSocketAddress(), code, reason);
    }

    @Override
    public void onMessage(WebSocket conn, String message) {
        if (message == null || message.isEmpty()) return;
        BotBridge.LOGGER.info("收到 bot 消息: {}", message);
        BotBridge.submitToGame(message);
    }

    @Override
    public void onError(WebSocket conn, Exception ex) {
        BotBridge.LOGGER.error("BotBridge 服务器出错", ex);
    }

    @Override
    public void onStart() {
        BotBridge.LOGGER.info("BotBridge WebSocket 服务器已启动: {}", getAddress());
    }

    public void broadcastChat(String senderName, String content) {
        // Python bot 端会自己加 sender 和时间戳前缀，这里只送原始内容，避免重复
        broadcastRaw(content);
    }

    public void broadcastGame(String content) {
        broadcastRaw(content);
    }

    private void broadcastRaw(String line) {
        for (WebSocket ws : clients) {
            try {
                ws.send(line);
            } catch (Exception e) {
                BotBridge.LOGGER.warn("向 bot 广播失败: {}", e.getMessage());
            }
        }
    }
}
