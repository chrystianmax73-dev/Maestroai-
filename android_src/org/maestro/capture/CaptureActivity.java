package org.maestro.capture;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

import org.kivy.android.PythonActivity;

/** Native bridge for the user-authorized MediaProjection flow. */
public class CaptureActivity extends PythonActivity {
    private static final int REQUEST_CAPTURE = 4901;
    private static final String RESULT_ACTION = "org.maestro.CAPTURE_RESULT";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_CAPTURE) return;

        if (resultCode == Activity.RESULT_OK && data != null) {
            try {
                Class<?> serviceClass = Class.forName("org.maestro.maestrogrid.ServiceCapture");
                serviceClass.getMethod("start", android.app.Activity.class, String.class)
                        .invoke(null, this, "capture");
            } catch (Throwable ignored) {
                // The service can report the actual startup error through its status file.
            }
        }

        // The generated p4a service needs a moment to initialize its receiver.
        new Handler(Looper.getMainLooper()).postDelayed(
                () -> sendResult(resultCode, data), 900);
    }

    private void sendResult(int resultCode, Intent data) {
        Intent intent = new Intent(RESULT_ACTION);
        intent.setPackage(getPackageName());
        intent.putExtra("result_code", resultCode);
        if (data != null) intent.putExtra("data_intent", data);
        sendBroadcast(intent);
    }
}
