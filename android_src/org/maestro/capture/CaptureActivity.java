package org.maestro.capture;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;

import org.kivy.android.PythonActivity;
import org.maestro.maestrogrid.ServiceCapture;

/**
 * Android consent/controller bridge for Maestro Vision.
 *
 * The Python UI asks for capture by broadcasting CAPTURE_REQUEST. This class
 * then performs the official Android consent flow and starts the existing
 * foreground capture service. No input injection is performed.
 */
public class CaptureActivity extends PythonActivity {
    private static final int REQUEST_CAPTURE = 4901;
    private static final String REQUEST_ACTION = "org.maestro.CAPTURE_REQUEST";
    private static final String RESULT_ACTION = "org.maestro.CAPTURE_RESULT";

    private boolean waitingForOverlay = false;
    private boolean captureRequested = false;
    private BroadcastReceiver requestReceiver;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                if (REQUEST_ACTION.equals(intent.getAction())) {
                    requestCaptureIfNeeded();
                }
            }
        };
        IntentFilter filter = new IntentFilter(REQUEST_ACTION);
        registerReceiver(requestReceiver, filter);
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
                Intent intent = new Intent(RESULT_ACTION);
                intent.setPackage(getPackageName());
                intent.putExtra("result_code", resultCode);
                intent.putExtra("data_intent", data);
                sendBroadcast(intent);
            }, 700);
        } catch (Throwable error) {
            captureRequested = false;
        }
    }

    @Override
    protected void onDestroy() {
        if (requestReceiver != null) {
            try {
                unregisterReceiver(requestReceiver);
            } catch (Exception ignored) {
            }
            requestReceiver = null;
        }
        super.onDestroy();
    }
}
