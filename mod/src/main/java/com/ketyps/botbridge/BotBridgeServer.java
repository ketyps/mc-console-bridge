package com.ketyps.botbridge;

import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;

import java.net.InetSocketAddress;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class BotBridgeServer extends WebSocketServer {

    private final Set<WebSocket> clients = ConcurrentHashMap.newKeySet();
    /** 每个连接是否已收到身份握手（本地玩家名），保证每条连接只发一次。 */
    private final Map<WebSocket, Boolean> identitySent = new ConcurrentHashMap<>();

    public BotBridgeServer(InetSocketAddress address) {
        super(address);
    }

    @Override
    public void onOpen(WebSocket conn, ClientHandshake handshake) {
        clients.add(conn);
        identitySent.put(conn, false);
        BotBridge.LOGGER.info("bot 客户端已连接: {}", conn.getRemoteSocketAddress());
        // 玩家已进游戏时立刻发身份握手；未进游戏时由后续广播路径补发
        sendIdentityIfReady(conn);
    }

    @Override
    public void onClose(WebSocket conn, int code, String reason, boolean remote) {
        clients.remove(conn);
        identitySent.remove(conn);
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

    /**
     * 向连接发送身份握手（JSON 单行）：{"type":"identity","name":"本地玩家名"}。
     * Python 端用它做自身回声过滤和控制台显示，无需手动配置 BOT_NAME。
     * 玩家名未就绪（如未进世界）时跳过，等后续广播时再补发。
     */
    private void sendIdentityIfReady(WebSocket conn) {
        if (Boolean.TRUE.equals(identitySent.get(conn))) return;
        String playerName = BotBridge.getLocalPlayerName();
        if (playerName == null) return;
        identitySent.put(conn, true);
        String line = "{\"type\":\"identity\",\"name\":\"" + playerName + "\"}";
        try {
            conn.send(line);
            BotBridge.LOGGER.info("已向 bot 发送身份握手: {}", playerName);
        } catch (Exception e) {
            BotBridge.LOGGER.warn("发送身份握手失败: {}", e.getMessage());
        }
    }

    public void broadcastChat(String senderName, String content) {
        // 以 "<玩家名> 内容" 的纯文本行转发，与 Python 端 sender_patterns 的默认模板
        // （"<{name}>,{name}:"）对齐。Python 端必须从消息里解析出说话人，
        // 才能做每玩家冷却、管理员指令权限校验和 @ 提及。
        // 注意：部分服务器/聊天插件会把 "<玩家名>" 或 "[玩家名]" 前缀直接编进消息文本
        // （message.getString() 已含前缀），此时不再重复拼接，避免 "<ketyps> <ketyps>" 双名前缀。
        if (!contentAlreadyHasSender(senderName, content)) {
            content = "<" + senderName + "> " + content;
        }
        broadcastRaw(content);
    }

    /** 判断消息文本是否已自带发送者前缀（仅识别无歧义的 <名字> / [名字] 形式，
     *  避免误伤"内容恰好以玩家名开头"的干净服务器）。 */
    private static boolean contentAlreadyHasSender(String senderName, String content) {
        return content.startsWith("<" + senderName + ">")
                || content.startsWith("[" + senderName + "]");
    }

    public void broadcastGame(String content) {
        broadcastRaw(content);
    }

    private void broadcastRaw(String line) {
        for (WebSocket ws : clients) {
            sendIdentityIfReady(ws); // 玩家名晚就绪时，在第一条聊天前补发身份
            try {
                ws.send(line);
            } catch (Exception e) {
                BotBridge.LOGGER.warn("向 bot 广播失败: {}", e.getMessage());
            }
        }
    }
}
