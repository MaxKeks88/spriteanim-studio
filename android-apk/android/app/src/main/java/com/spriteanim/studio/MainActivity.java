package com.spriteanim.studio;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.Window;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * SpriteAnim Studio для телефона: находит студию на компьютере в локальной сети
 * и открывает её интерфейс. Вся работа (ComfyUI, модели, файлы) — на ПК.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "spriteanim";
    private static final String PREF_URL = "url";
    private static final String PREF_RECENT = "recent";
    private static final int DISCOVERY_PORT = 8190;
    private static final int STUDIO_PORT = 8189;
    private static final int REQ_FILE = 41;
    private static final int REQ_MIC = 42;

    private WebView web;
    private ScrollView connectScroll;
    private TextView connStatus;
    private EditText addr;
    private Button connectBtn;
    private Button findBtn;
    private ProgressBar progress;
    private LinearLayout recentList;

    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest micRequest;
    private String serverHost = "";
    private long lastBack = 0L;
    private boolean pageLoaded = false;
    private boolean mainError = false;
    private boolean searchedOnce = false;

    private final Handler ui = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#0e1014"));
        w.setNavigationBarColor(Color.parseColor("#0e1014"));

        web = findViewById(R.id.web);
        connectScroll = findViewById(R.id.connectScroll);
        connStatus = findViewById(R.id.connStatus);
        addr = findViewById(R.id.addr);
        connectBtn = findViewById(R.id.connectBtn);
        findBtn = findViewById(R.id.findBtn);
        progress = findViewById(R.id.progress);
        recentList = findViewById(R.id.recentList);

        setupWebView();

        connectBtn.setOnClickListener(v -> {
            String url = normalizeUrl(addr.getText().toString());
            if (url == null) {
                connStatus.setText(R.string.bad_addr);
                connStatus.setTextColor(getColor(R.color.bad));
                return;
            }
            connect(url);
        });
        findBtn.setOnClickListener(v -> discover());

        renderRecent();

        String saved = prefs().getString(PREF_URL, "");
        if (!saved.isEmpty()) {
            addr.setText(saved.replaceFirst("^https?://", ""));
            connect(saved);
        } else {
            showConnect(getString(R.string.connect_hint), false);
            discover();
        }

        if (Build.VERSION.SDK_INT <= 28 && checkSelfPermission(
                android.Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, 43);
        }
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    // ---------------------------------------------------------------- WebView

    private void setupWebView() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUserAgentString(s.getUserAgentString() + " SpriteAnimStudioAndroid/2.0");
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            s.setSafeBrowsingEnabled(false);
        }
        web.setBackgroundColor(Color.parseColor("#0e1014"));
        web.addJavascriptInterface(new Bridge(), "Android");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String scheme = uri.getScheme() == null ? "" : uri.getScheme();
                String host = uri.getHost() == null ? "" : uri.getHost();
                if (("http".equals(scheme) || "https".equals(scheme)) && host.equals(serverHost)) {
                    return false;   // внутри студии
                }
                if ("http".equals(scheme) || "https".equals(scheme) || "mailto".equals(scheme)) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    } catch (Exception ignored) {
                    }
                    return true;
                }
                return false;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                mainError = false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
                if (mainError) {
                    return;
                }
                if (!pageLoaded) {
                    pageLoaded = true;
                    connectScroll.setVisibility(View.GONE);
                    web.setVisibility(View.VISIBLE);
                }
                view.evaluateJavascript(DOWNLOAD_JS, null);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    mainError = true;
                    pageLoaded = false;
                    String text = getString(R.string.offline);
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        text += "\n\n" + error.getDescription();
                    }
                    showConnect(text, true);
                    if (!searchedOnce) {
                        searchedOnce = true;
                        discover();
                    }
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress >= 100) {
                    progress.setVisibility(View.GONE);
                } else if (newProgress > 5) {
                    progress.setVisibility(View.VISIBLE);
                    progress.setIndeterminate(false);
                    progress.setProgress(newProgress);
                }
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (fileCallback != null) {
                    fileCallback.onReceiveValue(null);
                }
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                String[] types = params.getAcceptTypes();
                String type = "*/*";
                if (types != null && types.length > 0 && types[0] != null && !types[0].trim().isEmpty()) {
                    type = types[0].split(",")[0].trim();
                }
                intent.setType(type);
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    startActivityForResult(Intent.createChooser(intent, getString(R.string.app_name)), REQ_FILE);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }

            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                boolean wantsMic = false;
                for (String res : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res)) {
                        wantsMic = true;
                    }
                }
                if (!wantsMic) {
                    request.deny();
                    return;
                }
                if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                        == PackageManager.PERMISSION_GRANTED) {
                    request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                } else {
                    micRequest = request;
                    requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                }
            }
        });

        web.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String disposition,
                                        String mimeType, long contentLength) {
                downloadUrl(url, guessName(disposition, mimeType));
            }
        });
    }

    /** Скрипт: перехватывает ссылки скачивания и отдаёт файл Android-мосту. */
    private static final String DOWNLOAD_JS =
            "(function(){if(window.__spriteDl)return;window.__spriteDl=true;" +
            "document.addEventListener('click',function(e){" +
            "var a=e.target&&e.target.closest?e.target.closest('a[download]'):null;if(!a)return;" +
            "var href=a.getAttribute('href')||'';if(!href)return;" +
            "var name=a.getAttribute('download')||'';e.preventDefault();e.stopPropagation();" +
            "if(/^https?:/i.test(href)||href.indexOf('//')===0){" +
            "Android.downloadUrl(new URL(href,location.href).href,name);return;}" +
            "if(href.indexOf('blob:')===0||href.indexOf('data:')===0){" +
            "fetch(href).then(function(r){return r.blob();}).then(function(b){" +
            "var fr=new FileReader();fr.onload=function(){var s=String(fr.result||'');" +
            "var i=s.indexOf(',');Android.saveBase64(name||'file',b.type||'application/octet-stream'," +
            "i>=0?s.slice(i+1):'');};fr.readAsDataURL(b);})" +
            ".catch(function(){Android.downloadUrl(new URL(href,location.href).href,name);});}" +
            "},true);})();";

    // ------------------------------------------------------------ подключение

    private String normalizeUrl(String raw) {
        if (raw == null) {
            return null;
        }
        String text = raw.trim();
        if (text.isEmpty()) {
            return null;
        }
        if (!text.matches("^[a-zA-Z][a-zA-Z0-9+.-]*://.*")) {
            text = "http://" + text;
        }
        Uri uri = Uri.parse(text);
        String host = uri.getHost();
        if (host == null || host.isEmpty()) {
            return null;
        }
        if (!"http".equals(uri.getScheme()) && !"https".equals(uri.getScheme())) {
            return null;
        }
        int port = uri.getPort();
        StringBuilder sb = new StringBuilder();
        sb.append(uri.getScheme()).append("://").append(host).append(':')
                .append(port == -1 ? STUDIO_PORT : port);
        String path = uri.getEncodedPath();
        if (path != null && !path.isEmpty() && !"/".equals(path)) {
            sb.append(path);
        }
        return sb.toString();
    }

    private void connect(String url) {
        serverHost = Uri.parse(url).getHost();
        prefs().edit().putString(PREF_URL, url).apply();
        addRecent(url);
        pageLoaded = false;
        mainError = false;
        searchedOnce = false;
        connectScroll.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        progress.setVisibility(View.VISIBLE);
        progress.setIndeterminate(true);
        web.loadUrl(url);
    }

    private void showConnect(String message, boolean failed) {
        pageLoaded = false;
        web.stopLoading();
        progress.setVisibility(View.GONE);
        web.setVisibility(View.GONE);
        connectScroll.setVisibility(View.VISIBLE);
        connStatus.setText(message);
        connStatus.setTextColor(getColor(failed ? R.color.bad : R.color.muted));
        renderRecent();
    }

    private void discover() {
        findBtn.setEnabled(false);
        connStatus.setTextColor(getColor(R.color.muted));
        connStatus.setText(R.string.searching);
        new Thread(() -> {
            List<Discovery.Server> found = Discovery.find(this, DISCOVERY_PORT, STUDIO_PORT, 2600,
                    text -> ui.post(() -> {
                        connStatus.setTextColor(getColor(R.color.muted));
                        connStatus.setText(text);
                    }));
            ui.post(() -> {
                findBtn.setEnabled(true);
                if (found.isEmpty()) {
                    connStatus.setTextColor(getColor(R.color.bad));
                    connStatus.setText(R.string.not_found);
                    return;
                }
                for (Discovery.Server server : found) {
                    addRecent(server.url);
                }
                connect(found.get(0).url);
            });
        }).start();
    }

    // ------------------------------------------------------------ недавние

    private void addRecent(String url) {
        try {
            JSONArray arr = new JSONArray(prefs().getString(PREF_RECENT, "[]"));
            List<String> list = new ArrayList<>();
            list.add(url);
            for (int i = 0; i < arr.length() && list.size() < 5; i++) {
                String item = arr.optString(i, "");
                if (!item.isEmpty() && !item.equals(url)) {
                    list.add(item);
                }
            }
            JSONArray out = new JSONArray();
            for (String item : list) {
                out.put(item);
            }
            prefs().edit().putString(PREF_RECENT, out.toString()).apply();
        } catch (Exception ignored) {
        }
    }

    private void renderRecent() {
        if (recentList == null) {
            return;
        }
        recentList.removeAllViews();
        try {
            JSONArray arr = new JSONArray(prefs().getString(PREF_RECENT, "[]"));
            for (int i = 0; i < arr.length(); i++) {
                final String url = arr.optString(i, "");
                if (url.isEmpty()) {
                    continue;
                }
                Button chip = new Button(this);
                chip.setText(url.replaceFirst("^https?://", ""));
                chip.setAllCaps(false);
                chip.setTextSize(13);
                chip.setBackgroundTintList(android.content.res.ColorStateList.valueOf(
                        Color.parseColor("#171b23")));
                chip.setTextColor(Color.parseColor("#e8ecf4"));
                chip.setOnClickListener(v -> connect(url));
                recentList.addView(chip);
            }
        } catch (Exception ignored) {
        }
    }

    // ------------------------------------------------------------- скачивания

    private String guessName(String disposition, String mime) {
        String name = "";
        if (disposition != null) {
            int i = disposition.toLowerCase().indexOf("filename=");
            if (i >= 0) {
                name = disposition.substring(i + 9).replace("\"", "").trim();
                int semi = name.indexOf(';');
                if (semi > 0) {
                    name = name.substring(0, semi);
                }
            }
        }
        if (name.isEmpty()) {
            String ext = android.webkit.MimeTypeMap.getSingleton()
                    .getExtensionFromMimeType(mime == null ? "" : mime);
            name = "spriteanim-" + System.currentTimeMillis() + (ext == null ? "" : "." + ext);
        }
        return safeName(name);
    }

    private String safeName(String name) {
        String clean = (name == null ? "" : name).replaceAll("[\\\\/:*?\"<>|\\r\\n]+", "-").trim();
        if (clean.isEmpty()) {
            clean = "spriteanim-" + System.currentTimeMillis();
        }
        return clean.length() > 120 ? clean.substring(clean.length() - 120) : clean;
    }

    private String nameFromUrl(String url) {
        try {
            Uri u = Uri.parse(url);
            String fn = u.getQueryParameter("filename");
            if (fn != null && !fn.isEmpty()) {
                return fn;
            }
            String path = u.getPath() == null ? "" : u.getPath();
            String nm = u.getQueryParameter("name");
            if (nm != null && !nm.isEmpty()) {
                return path.endsWith("/api/zip") ? nm + ".zip" : nm;
            }
            String last = u.getLastPathSegment();
            return last == null ? "" : last;
        } catch (Exception ignored) {
            return "";
        }
    }

    private void downloadUrl(String url, String name) {
        String fileName = safeName(name);
        if (name == null || name.trim().isEmpty()) {
            fileName = safeName(nameFromUrl(url));
        }
        final String finalName = fileName;
        ui.post(() -> {
            try {
                DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                req.setTitle(finalName);
                req.setDescription(getString(R.string.downloading));
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, finalName);
                DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                dm.enqueue(req);
                Toast.makeText(this, getString(R.string.saved), Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, getString(R.string.save_failed), Toast.LENGTH_LONG).show();
            }
        });
    }

    private void saveBase64(String name, String mime, String base64) {
        final String fileName = safeName(name);
        try {
            byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
                values.put(MediaStore.MediaColumns.MIME_TYPE,
                        mime == null || mime.isEmpty() ? "application/octet-stream" : mime);
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                Uri uri = getContentResolver()
                        .insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (uri == null) {
                    throw new IllegalStateException("media store");
                }
                try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                    if (out == null) {
                        throw new IllegalStateException("output stream");
                    }
                    out.write(bytes);
                }
            } else {
                File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                File target = new File(dir, fileName);
                try (FileOutputStream out = new FileOutputStream(target)) {
                    out.write(bytes);
                }
            }
            ui.post(() -> Toast.makeText(this, getString(R.string.saved), Toast.LENGTH_SHORT).show());
        } catch (Exception e) {
            ui.post(() -> Toast.makeText(this, getString(R.string.save_failed), Toast.LENGTH_LONG).show());
        }
    }

    /** Мост для страницы: ссылки на файлы и большие двоичные ответы. */
    public class Bridge {
        @JavascriptInterface
        public void downloadUrl(String url, String name) {
            MainActivity.this.downloadUrl(url, name);
        }

        @JavascriptInterface
        public void saveBase64(String name, String mime, String data) {
            MainActivity.this.saveBase64(name, mime, data);
        }
    }

    // ------------------------------------------------------------ системное

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_FILE) {
            if (fileCallback != null) {
                Uri[] result = null;
                if (resultCode == RESULT_OK && data != null) {
                    if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        result = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            result[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    } else if (data.getData() != null) {
                        result = new Uri[]{data.getData()};
                    }
                }
                fileCallback.onReceiveValue(result);
                fileCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == REQ_MIC && micRequest != null) {
            boolean granted = results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED;
            if (granted) {
                micRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                micRequest.deny();
                Toast.makeText(this, R.string.mic_needed, Toast.LENGTH_LONG).show();
            }
            micRequest = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (pageLoaded) {
            if (web.canGoBack()) {
                web.goBack();
                return;
            }
            long now = System.currentTimeMillis();
            if (now - lastBack < 2200) {
                super.onBackPressed();
                return;
            }
            lastBack = now;
            new AlertDialog.Builder(this)
                    .setTitle(R.string.app_name)
                    .setItems(new CharSequence[]{
                            getString(R.string.change_server),
                            "Выйти"
                    }, (dialog, which) -> {
                        if (which == 0) {
                            showConnect(getString(R.string.connect_hint), false);
                            addr.setText(prefs().getString(PREF_URL, "")
                                    .replaceFirst("^https?://", ""));
                        } else {
                            finish();
                        }
                    })
                    .setNegativeButton("Отмена", null)
                    .show();
            return;
        }
        super.onBackPressed();
    }
}
