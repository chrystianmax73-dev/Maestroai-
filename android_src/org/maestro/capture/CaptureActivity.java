package org.maestro.capture;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;

import org.kivy.android.PythonActivity;
import org.maestro.maestrogrid.ServiceCapture;

/**
 * Kivy Activity wrapper that performs the Android consent flow for screen
 * capture. The actual frames are handled by the Python foreground service.
 */
public class CaptureActivity extends PythonActivity {
    private static final int REQUEST_CAPTURE = 4901;
    private boolean waitingForOverlay = false;
    private boolean captureRequested = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        new Handler(Looper.getMainLooper()).postDelayed(this::requestCaptureIfNeeded, 1200);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (waitingForOverlay) {
            waitingForOverlay = false;
            new Handler(Looper.getMainLooper()).postDelayed(this::requestCaptureIfNeeded, 250);
        }
    }

    private void requestCaptureIfNeeded() {
        if (captureRequested) {
            return;
        }
        if (android.os.Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            waitingForOverlay = true;
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
            return;
        }

        MediaProjectionManager manager =
                (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
        if (manager == null) {
            return;
        }
        captureRequested = true;
        startActivityForResult(manager.createScreenCaptureIntent(), REQUEST_CAPTURE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_CAPTURE) {
            return;
        }
        if (resultCode != Activity.RESULT_OK || data == null) {
            captureRequested = false;
            return;
        }

        try {
            ServiceCapture.start(this, "capture");
            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                Intent intent = new Intent("org.maestro.CAPTURE_RESULT");
                intent.setPackage(getPackageName());
                intent.putExtra("result_code", resultCode);
                intent.putExtra("data_intent", data);
                sendBroadcast(intent);
            }, 700);
        } catch (Throwable error) {
            captureRequested = false;
        }
    }
}
