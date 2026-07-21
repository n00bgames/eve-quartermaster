package app.evequartermaster.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.text.InputType;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class ServerSettingsDialog {
    public interface Listener {
        void onServerSelected(String serverUrl);
    }

    private static final int ACCENT = Color.parseColor("#e8b84d");
    private static final int TEXT = Color.parseColor("#f0f4f8");
    private static final int MUTED = Color.parseColor("#a9b6c5");
    private static final int SURFACE = Color.parseColor("#111820");

    private ServerSettingsDialog() {
    }

    public static void show(Activity activity, String currentUrl, boolean firstLaunch, Listener listener) {
        int padding = dp(activity, 24);
        LinearLayout content = new LinearLayout(activity);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(padding, dp(activity, 8), padding, 0);

        TextView description = new TextView(activity);
        description.setText(firstLaunch
                ? "Enter the address where this device can reach your EVE Quartermaster installation."
                : "Change the EQM installation loaded by this app. Your sign-in is stored separately by each server.");
        description.setTextColor(MUTED);
        description.setTextSize(15);
        description.setPadding(0, 0, 0, dp(activity, 16));
        content.addView(description, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        EditText input = new EditText(activity);
        input.setText(currentUrl);
        input.setHint("https://eqm.example.com/");
        input.setSingleLine(true);
        input.setSelectAllOnFocus(true);
        input.setTextColor(TEXT);
        input.setHintTextColor(MUTED);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        content.addView(input, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle(firstLaunch ? "Connect to EVE Quartermaster" : "Server settings")
                .setView(content)
                .setPositiveButton("Save and open", null)
                .setNeutralButton("Build default", null)
                .setNegativeButton(firstLaunch ? null : "Cancel", null)
                .create();
        dialog.setCancelable(!firstLaunch);
        dialog.setCanceledOnTouchOutside(!firstLaunch);
        dialog.setOnShowListener(unused -> {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(SURFACE));
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(ACCENT);
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setTextColor(ACCENT);
            if (!firstLaunch) {
                dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(MUTED);
            }
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
                try {
                    String normalized = ServerUrlStore.normalize(input.getText().toString());
                    input.setError(null);
                    listener.onServerSelected(normalized);
                    dialog.dismiss();
                } catch (IllegalArgumentException error) {
                    input.setError(error.getMessage());
                    input.requestFocus();
                }
            });
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(view -> {
                String normalized = ServerUrlStore.normalize(BuildConfig.EQM_URL);
                listener.onServerSelected(normalized);
                dialog.dismiss();
            });
        });
        dialog.show();
    }

    private static int dp(Activity activity, int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }
}