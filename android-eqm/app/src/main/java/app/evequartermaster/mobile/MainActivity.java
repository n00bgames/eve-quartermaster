package app.evequartermaster.mobile;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.parseColor("#070b0f"));
        getWindow().setNavigationBarColor(Color.parseColor("#070b0f"));
        setupWebView();
        if (ServerUrlStore.hasSavedUrl(this)) {
            openServer(ServerUrlStore.getUrl(this));
        } else {
            showServerSettings(true);
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        webView.setBackgroundColor(Color.parseColor("#070b0f"));

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new EqmWebViewClient());

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#070b0f"));
        root.addView(createToolbar());
        root.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1
        ));
        setContentView(root);
    }

    private FrameLayout createToolbar() {
        FrameLayout toolbar = new FrameLayout(this);
        toolbar.setBackgroundColor(Color.parseColor("#0b1117"));
        toolbar.setPadding(dp(14), 0, dp(4), 0);
        toolbar.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(48)
        ));

        TextView title = new TextView(this);
        title.setText("EVE Quartermaster");
        title.setTextColor(Color.parseColor("#f0f4f8"));
        title.setTextSize(16);
        title.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.addView(title, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        toolbar.addView(createSettingsButton());
        return toolbar;
    }

    private ImageButton createSettingsButton() {
        ImageButton button = new ImageButton(this);
        button.setImageResource(android.R.drawable.ic_menu_preferences);
        button.setColorFilter(Color.parseColor("#f0f4f8"));
        button.setContentDescription("Server settings");
        button.setTooltipText("Server settings");
        button.setPadding(dp(11), dp(11), dp(11), dp(11));

        GradientDrawable background = new GradientDrawable();
        background.setShape(GradientDrawable.OVAL);
        background.setColor(Color.parseColor("#ee111820"));
        background.setStroke(dp(1), Color.parseColor("#4fb3c7"));
        button.setBackground(background);
        button.setOnClickListener(view -> showServerSettings(false));

        FrameLayout.LayoutParams layout = new FrameLayout.LayoutParams(dp(44), dp(44));
        layout.gravity = Gravity.CENTER_VERTICAL | Gravity.END;
        layout.setMargins(dp(4), 0, dp(4), 0);
        button.setLayoutParams(layout);
        return button;
    }

    private void showServerSettings(boolean firstLaunch) {
        ServerSettingsDialog.show(
                this,
                ServerUrlStore.getUrl(this),
                firstLaunch,
                serverUrl -> {
                    ServerUrlStore.saveUrl(this, serverUrl);
                    openServer(serverUrl);
                }
        );
    }

    private void openServer(String serverUrl) {
        webView.clearHistory();
        webView.loadUrl(serverUrl);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    private class EqmWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            String scheme = uri.getScheme();

            if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
                return false;
            }

            try {
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
            } catch (ActivityNotFoundException ex) {
                Toast.makeText(MainActivity.this, "No app can open this link.", Toast.LENGTH_SHORT).show();
            }
            return true;
        }
    }
}