package org.bmtts.bmtextspeech;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.appopen.AppOpenAd;

/**
 * Native cold-start loading activity.
 *
 * App Open is loaded and displayed before the SDL/Kivy activity exists. This
 * prevents a full-screen Android ad from being attached to or removed from an
 * active SDL rendering surface. Failure, no fill, or timeout always continues
 * to the application.
 */
public final class BmLaunchActivity extends Activity {
    private static final String TEST_APP_OPEN_ID =
            "ca-app-pub-3940256099942544/9257395921";
    private static final long MAX_WAIT_MS = 5500L;
    private static boolean attemptedInProcess = false;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean completed = false;
    private AppOpenAd appOpenAd = null;

    private final Runnable timeoutRunnable = new Runnable() {
        @Override
        public void run() {
            continueToKivy();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        super.onCreate(savedInstanceState);
        showLoadingScreen();

        if (useTestAds()) {
            continueToKivy();
            return;
        }

        if (attemptedInProcess) {
            continueToKivy();
            return;
        }
        attemptedInProcess = true;

        handler.postDelayed(timeoutRunnable, MAX_WAIT_MS);
        try {
            MobileAds.initialize(getApplicationContext());
            loadAppOpen();
        } catch (Throwable ignored) {
            continueToKivy();
        }
    }

    @Override
    protected void onResume() {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        super.onResume();
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        super.onConfigurationChanged(newConfig);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        if (hasFocus) {
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        }
        super.onWindowFocusChanged(hasFocus);
    }

    private void showLoadingScreen() {
        getWindow().setStatusBarColor(Color.rgb(12, 18, 28));
        getWindow().setNavigationBarColor(Color.rgb(12, 18, 28));

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(12, 18, 28));

        TextView brand = new TextView(this);
        brand.setText("BM\nText to Voice");
        brand.setTextColor(Color.WHITE);
        brand.setTextSize(25f);
        brand.setGravity(Gravity.CENTER);
        brand.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        FrameLayout.LayoutParams brandParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        brandParams.gravity = Gravity.CENTER;
        brandParams.leftMargin = dp(24);
        brandParams.rightMargin = dp(24);
        root.addView(brand, brandParams);

        ProgressBar progress = new ProgressBar(this);
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
                dp(34),
                dp(34)
        );
        progressParams.gravity = Gravity.CENTER_HORIZONTAL | Gravity.BOTTOM;
        progressParams.bottomMargin = dp(82);
        root.addView(progress, progressParams);

        setContentView(root);
    }

    private void loadAppOpen() {
        final String unitId = resolveAppOpenUnitId();
        if (unitId == null || unitId.trim().isEmpty()) {
            continueToKivy();
            return;
        }

        AppOpenAd.load(
                this,
                unitId,
                new AdRequest.Builder().build(),
                new AppOpenAd.AppOpenAdLoadCallback() {
                    @Override
                    public void onAdLoaded(AppOpenAd loadedAd) {
                        if (completed || isFinishing() || isDestroyed()) {
                            return;
                        }
                        appOpenAd = loadedAd;
                        handler.removeCallbacks(timeoutRunnable);
                        showLoadedAd();
                    }

                    @Override
                    public void onAdFailedToLoad(LoadAdError error) {
                        continueToKivy();
                    }
                }
        );
    }

    private void showLoadedAd() {
        if (appOpenAd == null || completed || isFinishing() || isDestroyed()) {
            continueToKivy();
            return;
        }

        appOpenAd.setFullScreenContentCallback(new FullScreenContentCallback() {
            @Override
            public void onAdDismissedFullScreenContent() {
                appOpenAd = null;
                continueToKivy();
            }

            @Override
            public void onAdFailedToShowFullScreenContent(AdError error) {
                appOpenAd = null;
                continueToKivy();
            }

            @Override
            public void onAdShowedFullScreenContent() {
                appOpenAd = null;
            }
        });

        try {
            appOpenAd.show(this);
        } catch (Throwable ignored) {
            continueToKivy();
        }
    }

    private String resolveAppOpenUnitId() {
        try {
            ApplicationInfo info = getPackageManager().getApplicationInfo(
                    getPackageName(),
                    PackageManager.GET_META_DATA
            );
            Bundle metadata = info.metaData;
            if (metadata != null && metadata.getBoolean("BM_USE_TEST_ADS", false)) {
                return TEST_APP_OPEN_ID;
            }
            return metadata == null
                    ? null
                    : metadata.getString("BM_APP_OPEN_UNIT_ID");
        } catch (Throwable ignored) {
            return null;
        }
    }

    private boolean useTestAds() {
        try {
            ApplicationInfo info = getPackageManager().getApplicationInfo(
                    getPackageName(),
                    PackageManager.GET_META_DATA
            );
            Bundle metadata = info.metaData;
            return metadata != null && metadata.getBoolean("BM_USE_TEST_ADS", false);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private synchronized void continueToKivy() {
        if (completed) {
            return;
        }
        completed = true;
        handler.removeCallbacks(timeoutRunnable);
        try {
            Intent intent = new Intent(this, BmPythonActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            startActivity(intent);
        } finally {
            finish();
            overridePendingTransition(0, 0);
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(timeoutRunnable);
        super.onDestroy();
    }
}
