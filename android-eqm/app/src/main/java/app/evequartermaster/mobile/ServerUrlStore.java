package app.evequartermaster.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;

public final class ServerUrlStore {
    private static final String PREFS_NAME = "eqm_mobile_preferences";
    private static final String KEY_SERVER_URL = "server_url";

    private ServerUrlStore() {
    }

    public static boolean hasSavedUrl(Context context) {
        return preferences(context).contains(KEY_SERVER_URL);
    }

    public static String getUrl(Context context) {
        return preferences(context).getString(KEY_SERVER_URL, BuildConfig.EQM_URL);
    }

    public static void saveUrl(Context context, String url) {
        preferences(context).edit().putString(KEY_SERVER_URL, normalize(url)).apply();
    }

    public static String normalize(String rawUrl) {
        String value = rawUrl == null ? "" : rawUrl.trim();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Enter the address of your EQM server.");
        }
        if (!value.contains("://")) {
            value = "http://" + value;
        }

        Uri uri = Uri.parse(value);
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) {
            throw new IllegalArgumentException("The server address must use http:// or https://.");
        }
        if (uri.getHost() == null || uri.getHost().trim().isEmpty()) {
            throw new IllegalArgumentException("Enter a complete server address or local IP address.");
        }
        if (uri.getQuery() != null || uri.getFragment() != null) {
            throw new IllegalArgumentException("Use the EQM server address without a query or page fragment.");
        }
        return value.endsWith("/") ? value : value + "/";
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }
}