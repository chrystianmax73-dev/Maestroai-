package org.maestro.capture;

import android.content.Context;
import android.content.Intent;
import android.media.projection.MediaProjection;

/**
 * Native callback required by MediaProjection. It only notifies the local
 * capture service that the user/system stopped the projection.
 */
public final class ProjectionCallback extends MediaProjection.Callback {
    private final Context context;

    public ProjectionCallback(Context context) {
        this.context = context.getApplicationContext();
    }

    @Override
    public void onStop() {
        Intent intent = new Intent("org.maestro.CAPTURE_STOP");
        intent.setPackage(context.getPackageName());
        context.sendBroadcast(intent);
    }
}
