package com.spriteanim.studio;

import android.content.Context;
import android.net.DhcpInfo;
import android.net.wifi.WifiManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Поиск студии в локальной сети — так же, как в рабочем ComfyPult:
 *   1. UDP-broadcast (обычный Wi-Fi и точка доступа);
 *   2. направленный broadcast в подсеть и известные подсети телефона;
 *   3. прямой перебор адресов по порту студии (если broadcast режется).
 */
public final class Discovery {

    public interface Stage {
        void on(String text);
    }

    public static final class Server {
        public final String url;
        public final String name;

        Server(String url, String name) {
            this.url = url;
            this.name = name == null || name.isEmpty() ? url : name;
        }
    }

    private static final int SCAN_WORKERS = 64;
    private static final int SCAN_CONNECT_TIMEOUT = 200;
    private static final String MAGIC = "SPRITEANIM-DISCOVER-1";

    /** Подсети, которые обычно выдаёт точка доступа на телефоне. */
    private static final String[] HOTSPOT_PREFIXES = {
            "192.168.43",   // Android по умолчанию
            "192.168.42",   // старые Android
            "192.168.137",  // Windows Mobile Hotspot
            "172.20.10",    // iPhone
            "192.168.0",
            "192.168.1",
            "10.0.0",
            "10.0.1"
    };

    private Discovery() {}

    public static List<Server> find(Context ctx, int discoveryPort, int httpPort,
                                    int timeoutMs, Stage stage) {
        List<Server> found = findByBroadcast(ctx, discoveryPort, timeoutMs, stage);
        if (!found.isEmpty()) {
            return found;
        }
        if (stage != null) {
            stage.on("Сканирую сеть…");
        }
        return scanNetwork(ctx, httpPort);
    }

    /* ─────────────────────────────────────────────── UDP */

    private static List<Server> findByBroadcast(Context ctx, int port, int timeoutMs, Stage stage) {
        List<Server> out = new ArrayList<>();
        DatagramSocket socket = null;
        try {
            socket = new DatagramSocket();
            socket.setBroadcast(true);
            socket.setSoTimeout(250);
            byte[] payload = MAGIC.getBytes(StandardCharsets.UTF_8);

            Set<String> targets = new LinkedHashSet<>();
            targets.add("255.255.255.255");
            for (String prefix : localPrefixes()) {
                targets.add(prefix + ".255");
            }
            String dhcpBroadcast = subnetBroadcast(ctx);
            if (dhcpBroadcast != null) {
                targets.add(dhcpBroadcast);
            }
            for (String prefix : HOTSPOT_PREFIXES) {
                targets.add(prefix + ".255");
            }

            long deadline = System.currentTimeMillis() + timeoutMs;
            while (System.currentTimeMillis() < deadline) {
                for (String target : targets) {
                    try {
                        socket.send(new DatagramPacket(payload, payload.length,
                                InetAddress.getByName(target), port));
                    } catch (Exception ignored) {
                    }
                }
                long slice = Math.min(System.currentTimeMillis() + 600, deadline);
                while (System.currentTimeMillis() < slice) {
                    try {
                        byte[] buf = new byte[2048];
                        DatagramPacket packet = new DatagramPacket(buf, buf.length);
                        socket.receive(packet);
                        String text = new String(packet.getData(), 0, packet.getLength(),
                                StandardCharsets.UTF_8).trim();
                        Server server = parseReply(text, packet.getAddress().getHostAddress());
                        if (server != null && !has(out, server.url)) {
                            out.add(server);
                        }
                    } catch (java.net.SocketTimeoutException ignored) {
                        // ждём дальше
                    }
                }
            }
        } catch (Exception ignored) {
        } finally {
            if (socket != null) {
                socket.close();
            }
        }
        return out;
    }

    private static Server parseReply(String text, String senderIp) {
        try {
            JSONObject obj = new JSONObject(text);
            if (!"spriteanim-studio".equals(obj.optString("app"))) {
                return null;
            }
            String name = obj.optString("hostname", senderIp);
            JSONArray urls = obj.optJSONArray("urls");
            if (urls != null && urls.length() > 0) {
                return new Server(urls.getString(0), name);
            }
            int port = obj.optInt("port", 8189);
            return new Server("http://" + senderIp + ":" + port, name);
        } catch (Exception ignored) {
            return null;
        }
    }

    /* ─────────────────────────────────────────────── сканирование */

    private static List<Server> scanNetwork(Context ctx, int httpPort) {
        Set<String> prefixes = new LinkedHashSet<>(localPrefixes());
        Collections.addAll(prefixes, HOTSPOT_PREFIXES);

        long deadline = System.currentTimeMillis() + 12000;
        for (String prefix : prefixes) {
            if (System.currentTimeMillis() > deadline) {
                break;
            }
            List<Server> hits = scanSubnet(prefix, httpPort);
            if (!hits.isEmpty()) {
                return hits;
            }
        }
        return new ArrayList<>();
    }

    private static List<Server> scanSubnet(final String prefix, final int httpPort) {
        final List<Server> hits = Collections.synchronizedList(new ArrayList<Server>());
        final AtomicInteger index = new AtomicInteger(1);
        final AtomicBoolean stop = new AtomicBoolean(false);

        Thread[] workers = new Thread[SCAN_WORKERS];
        for (int w = 0; w < SCAN_WORKERS; w++) {
            workers[w] = new Thread(() -> {
                while (!stop.get()) {
                    int host = index.getAndIncrement();
                    if (host > 254) {
                        return;
                    }
                    String ip = prefix + "." + host;
                    if (!isOpen(ip, httpPort)) {
                        continue;
                    }
                    Server server = hello(ip, httpPort);
                    if (server != null) {
                        hits.add(server);
                        stop.set(true);
                        return;
                    }
                }
            });
            workers[w].setDaemon(true);
            workers[w].start();
        }

        long deadline = System.currentTimeMillis() + 3000;
        for (Thread t : workers) {
            long left = deadline - System.currentTimeMillis();
            if (left <= 0) {
                break;
            }
            try {
                t.join(left);
            } catch (InterruptedException ignored) {
            }
        }
        stop.set(true);
        return new ArrayList<>(hits);
    }

    private static boolean isOpen(String ip, int port) {
        Socket socket = new Socket();
        try {
            socket.connect(new InetSocketAddress(ip, port), SCAN_CONNECT_TIMEOUT);
            return true;
        } catch (Exception e) {
            return false;
        } finally {
            try {
                socket.close();
            } catch (Exception ignored) {
            }
        }
    }

    /** Это студия? Проверяем /api/net по имени приложения. */
    private static Server hello(String ip, int port) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL("http://" + ip + ":" + port + "/api/net")
                    .openConnection();
            conn.setConnectTimeout(900);
            conn.setReadTimeout(900);
            if (conn.getResponseCode() != 200) {
                return null;
            }
            StringBuilder body = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null && body.length() < 8192) {
                    body.append(line);
                }
            }
            JSONObject obj = new JSONObject(body.toString());
            if (!"spriteanim-studio".equals(obj.optString("app"))) {
                return null;
            }
            String name = obj.optString("hostname", ip);
            return new Server("http://" + ip + ":" + port, name);
        } catch (Exception e) {
            return null;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /* ─────────────────────────────────────────────── подсети */

    /** Локальные IPv4-подсети вида "192.168.43" (без последнего октета). */
    private static Set<String> localPrefixes() {
        List<String> wifi = new ArrayList<>();
        List<String> other = new ArrayList<>();
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces != null && interfaces.hasMoreElements()) {
                NetworkInterface ni = interfaces.nextElement();
                if (!ni.isUp() || ni.isLoopback()) {
                    continue;
                }
                String name = ni.getName() == null ? "" : ni.getName().toLowerCase(Locale.ROOT);
                if (name.startsWith("rmnet") || name.startsWith("tun")
                        || name.startsWith("dummy") || name.startsWith("p2p")) {
                    continue;   // мобильный интернет и VPN не помогут найти ПК
                }
                boolean lan = name.startsWith("wlan") || name.startsWith("ap")
                        || name.startsWith("softap") || name.startsWith("swlan")
                        || name.startsWith("eth");
                Enumeration<InetAddress> addrs = ni.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    InetAddress a = addrs.nextElement();
                    if (!(a instanceof Inet4Address)) {
                        continue;
                    }
                    String ip = a.getHostAddress();
                    int dot = ip.lastIndexOf('.');
                    if (dot <= 0) {
                        continue;
                    }
                    String prefix = ip.substring(0, dot);
                    if (lan) {
                        wifi.add(prefix);
                    } else {
                        other.add(prefix);
                    }
                }
            }
        } catch (Exception ignored) {
        }
        Set<String> out = new LinkedHashSet<>(wifi);
        out.addAll(other);
        return out;
    }

    private static String subnetBroadcast(Context ctx) {
        try {
            WifiManager wm = (WifiManager) ctx.getApplicationContext()
                    .getSystemService(Context.WIFI_SERVICE);
            if (wm == null) {
                return null;
            }
            DhcpInfo info = wm.getDhcpInfo();
            if (info == null || info.ipAddress == 0 || info.netmask == 0) {
                return null;
            }
            int bc = (info.ipAddress & info.netmask) | ~info.netmask;
            return (bc & 0xff) + "." + ((bc >> 8) & 0xff) + "."
                    + ((bc >> 16) & 0xff) + "." + ((bc >> 24) & 0xff);
        } catch (Exception e) {
            return null;
        }
    }

    private static boolean has(List<Server> list, String url) {
        for (Server s : list) {
            if (s.url.equals(url)) {
                return true;
            }
        }
        return false;
    }
}
