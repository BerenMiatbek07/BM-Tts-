package org.bmtts.bmtextspeech;

import android.app.Activity;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdListener;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.interstitial.InterstitialAd;
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.compressors.bzip2.BZip2CompressorInputStream;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/** Native banner/interstitial bridge for the already-running Kivy screen. */
public final class BmAdMobBridge {
    private static final String TEST_BANNER_ID =
            "ca-app-pub-3940256099942544/6300978111";
    private static final String TEST_INTERSTITIAL_ID =
            "ca-app-pub-3940256099942544/1033173712";

    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final Map<String, BannerState> BANNERS = new HashMap<>();
    private static boolean initialized = false;
    private static FrameLayout overlay = null;
    private static boolean isLoadingInterstitial = false;
    private static boolean isShowingInterstitial = false;
    private static InterstitialAd interstitialAd = null;
    private static boolean bannersSuspended = false;
    // The Python layer reaches this class through PyJNIus already.  Keep the
    // downloaded-Piper bridge here as well, so release shrinking cannot remove
    // it as an apparently-unused Java class.
    private static BmSherpaTtsBridge sherpaTts = null;
    private static String sherpaModelDirectory = "";

    private static final class BannerState {
        AdView view;
        boolean loaded = false;
        boolean requestedVisible = false;
        int left = Integer.MIN_VALUE;
        int top = Integer.MIN_VALUE;
        int width = -1;
        int height = -1;
        int appliedVisibility = -1;
    }

    private BmAdMobBridge() {
    }

    public static void initialize(final Activity activity, final String ignoredAppOpenId) {
        if (!isActivityUsable(activity)) {
            return;
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    ensureInitialized(activity);
                } catch (Throwable ignored) {
                    // Ads never own app startup.
                }
            }
        });
    }

    /**
     * Extract a verified Piper archive. This resides on the bridge that is
     * already resolved by PyJNIus for every AdMob-enabled build.
     */
    public static void extractTarBz2(String archivePath, String destinationPath)
            throws IOException {
        File archive = new File(archivePath);
        File destination = new File(destinationPath);
        if (!archive.isFile()) {
            throw new IOException("Archive does not exist");
        }
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("Could not create destination");
        }

        String root = destination.getCanonicalPath() + File.separator;
        byte[] buffer = new byte[128 * 1024];
        try (
                BufferedInputStream fileInput = new BufferedInputStream(
                        new FileInputStream(archive), buffer.length);
                BZip2CompressorInputStream bzipInput =
                        new BZip2CompressorInputStream(fileInput, true);
                TarArchiveInputStream tarInput = new TarArchiveInputStream(bzipInput)
        ) {
            TarArchiveEntry entry;
            while ((entry = tarInput.getNextTarEntry()) != null) {
                if (entry.isSymbolicLink() || entry.isLink()) {
                    throw new IOException("Archive links are not allowed");
                }
                File output = new File(destination, entry.getName());
                if (!output.getCanonicalPath().startsWith(root)) {
                    throw new IOException("Unsafe archive path");
                }
                if (entry.isDirectory()) {
                    if (!output.exists() && !output.mkdirs()) {
                        throw new IOException("Could not create directory");
                    }
                    continue;
                }
                File parent = output.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("Could not create directory");
                }
                try (BufferedOutputStream target = new BufferedOutputStream(
                        new FileOutputStream(output), buffer.length)) {
                    int count;
                    while ((count = tarInput.read(buffer)) != -1) {
                        target.write(buffer, 0, count);
                    }
                    target.flush();
                }
            }
        }
    }

    /** Generate one WAV chunk from an installed Piper/Sherpa model. */
    public static synchronized boolean synthesizeSherpaToWave(
            Activity activity,
            String modelDirectory,
            int numThreads,
            String text,
            int speakerId,
            float speed,
            String outputPath
    ) throws IOException {
        String normalizedDirectory = new File(modelDirectory).getCanonicalPath();
        if (sherpaTts == null || !normalizedDirectory.equals(sherpaModelDirectory)) {
            releaseSherpa();
            sherpaTts = new BmSherpaTtsBridge(
                    activity,
                    normalizedDirectory,
                    Math.max(1, Math.min(6, numThreads))
            );
            sherpaModelDirectory = normalizedDirectory;
        }
        return sherpaTts.synthesizeToWave(text, speakerId, speed, outputPath);
    }

    /** Releases memory held by an offline voice after generation finishes. */
    public static synchronized void releaseSherpa() {
        if (sherpaTts != null) {
            sherpaTts.release();
            sherpaTts = null;
        }
        sherpaModelDirectory = "";
    }

    /** App Open is intentionally owned only by BmLaunchActivity. */
    public static void loadAppOpenAd(Activity activity, String unitId) {
        // no-op by design
    }

    /** App Open is intentionally owned only by BmLaunchActivity. */
    public static void loadAndShowAppOpenAd(Activity activity, String unitId) {
        // no-op by design
    }

    public static void loadBanner(
            final Activity activity,
            final String slot,
            final String liveBannerAdUnitId
    ) {
        if (!isActivityUsable(activity) || liveBannerAdUnitId == null) {
            return;
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    ensureInitialized(activity);
                    BannerState state = BANNERS.get(slot);
                    if (state == null) {
                        state = new BannerState();
                        state.view = new AdView(activity);
                        state.view.setAdSize(AdSize.BANNER);
                        state.view.setAdUnitId(resolveUnitId(activity, liveBannerAdUnitId, TEST_BANNER_ID));
                        state.view.setAdListener(new AdListener() {
                            @Override
                            public void onAdLoaded() {
                                state.loaded = true;
                                applyBannerFrame(state);
                            }
                            @Override
                            public void onAdFailedToLoad(LoadAdError error) {
                                state.loaded = false;
                                applyBannerFrame(state);
                            }
                        });
                        overlay.addView(state.view);
                        BANNERS.put(slot, state);
                    }
                    state.view.loadAd(new AdRequest.Builder().build());
                } catch (Throwable ignored) {
                    // no-op
                }
            }
        });
    }

    public static void setBannerVisibility(
            final Activity activity,
            final String slot,
            final boolean visible,
            final int left,
            final int top,
            final int width,
            final int height
    ) {
        if (activity == null) {
            return;
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                BannerState state = BANNERS.get(slot);
                if (state == null) {
                    return;
                }
                state.requestedVisible = visible;
                state.left = left;
                state.top = top;
                state.width = width;
                state.height = height;
                applyBannerFrame(state);
            }
        });
    }

    private static void applyBannerFrame(BannerState state) {
        if (state == null || state.view == null) {
            return;
        }
        if (state.left != Integer.MIN_VALUE && state.top != Integer.MIN_VALUE) {
            FrameLayout.LayoutParams current = (FrameLayout.LayoutParams) state.view.getLayoutParams();
            if (current == null) {
                current = new FrameLayout.LayoutParams(1, 1);
            }
            current.gravity = Gravity.TOP | Gravity.LEFT;
            current.leftMargin = state.left;
            current.topMargin = state.top;
            current.width = state.width;
            current.height = state.height;
            state.view.setLayoutParams(current);
        }

        int visibility = state.loaded && state.requestedVisible && !bannersSuspended
                ? View.VISIBLE
                : View.GONE;
        if (state.appliedVisibility != visibility) {
            state.appliedVisibility = visibility;
            state.view.setVisibility(visibility);
        }
    }

    /** Hide native views before SDL loses its surface and restore them later. */
    public static void setBannersSuspended(final Activity activity, final boolean suspended) {
        if (activity == null) {
            return;
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                bannersSuspended = suspended;
                if (overlay != null) {
                    overlay.setVisibility(suspended ? View.GONE : View.VISIBLE);
                }
                for (BannerState state : BANNERS.values()) {
                    applyBannerFrame(state);
                }
            }
        });
    }

    public static void loadInterstitialAd(
            final Activity activity,
            final String liveInterstitialUnitId
    ) {
        if (!isActivityUsable(activity) || liveInterstitialUnitId == null) {
            return;
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    ensureInitialized(activity);
                    MAIN.postDelayed(new Runnable() {
                        @Override
                        public void run() {
                            loadInterstitialOnUiThread(
                                    activity,
                                    resolveUnitId(
                                            activity,
                                            liveInterstitialUnitId,
                                            TEST_INTERSTITIAL_ID
                                    )
                            );
                        }
                    }, 2200L);
                } catch (Throwable ignored) {
                    // no-op
                }
            }
        });
    }

    public static void showInterstitialAd(
            final Activity activity,
            final String liveInterstitialUnitId
    ) {
        if (!isActivityUsable(activity) || liveInterstitialUnitId == null) {
            return;
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (isShowingInterstitial) {
                    return;
                }
                final String unitId = resolveUnitId(
                        activity,
                        liveInterstitialUnitId,
                        TEST_INTERSTITIAL_ID
                );
                if (interstitialAd == null) {
                    loadInterstitialOnUiThread(activity, unitId);
                    return;
                }

                final InterstitialAd adToShow = interstitialAd;
                interstitialAd = null;
                adToShow.setFullScreenContentCallback(
                        new FullScreenContentCallback() {
                            @Override
                            public void onAdDismissedFullScreenContent() {
                                isShowingInterstitial = false;
                                loadInterstitialOnUiThread(activity, unitId);
                            }

                            @Override
                            public void onAdFailedToShowFullScreenContent(AdError error) {
                                isShowingInterstitial = false;
                                loadInterstitialOnUiThread(activity, unitId);
                            }

                            @Override
                            public void onAdShowedFullScreenContent() {
                                isShowingInterstitial = true;
                            }
                        }
                );
                try {
                    isShowingInterstitial = true;
                    adToShow.show(activity);
                } catch (Throwable ignored) {
                    isShowingInterstitial = false;
                    loadInterstitialOnUiThread(activity, unitId);
                }
            }
        });
    }

    private static void loadInterstitialOnUiThread(
            final Activity activity,
            final String unitId
    ) {
        if (!isActivityUsable(activity)
                || isLoadingInterstitial
                || interstitialAd != null
                || isShowingInterstitial) {
            return;
        }
        isLoadingInterstitial = true;
        InterstitialAd.load(
                activity,
                unitId,
                new AdRequest.Builder().build(),
                new InterstitialAdLoadCallback() {
                    @Override
                    public void onAdLoaded(InterstitialAd loadedAd) {
                        interstitialAd = loadedAd;
                        isLoadingInterstitial = false;
                    }

                    @Override
                    public void onAdFailedToLoad(LoadAdError error) {
                        interstitialAd = null;
                        isLoadingInterstitial = false;
                    }
                }
        );
    }

    private static void ensureInitialized(Activity activity) {
        if (initialized && overlay != null && overlay.getParent() != null) {
            return;
        }

        MobileAds.initialize(activity.getApplicationContext());
        View rootView = activity.findViewById(android.R.id.content);
        if (!(rootView instanceof ViewGroup)) {
            return;
        }

        overlay = new FrameLayout(activity);
        overlay.setBackgroundColor(Color.TRANSPARENT);
        overlay.setClipChildren(false);
        overlay.setClipToPadding(false);
        overlay.setClickable(false);
        overlay.setFocusable(false);
        overlay.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        ((ViewGroup) rootView).addView(
                overlay,
                new ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT
                )
        );
        overlay.bringToFront();
        initialized = true;
    }

    private static String resolveUnitId(
            Activity activity,
            String liveId,
            String testId
    ) {
        return useTestAds(activity) ? testId : liveId;
    }

    private static boolean useTestAds(Activity activity) {
        try {
            ApplicationInfo info = activity.getPackageManager().getApplicationInfo(
                    activity.getPackageName(),
                    PackageManager.GET_META_DATA
            );
            Bundle metadata = info.metaData;
            return metadata != null && metadata.getBoolean("BM_USE_TEST_ADS", false);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static boolean isActivityUsable(Activity activity) {
        return activity != null && !activity.isFinishing() && !activity.isDestroyed();
    }

    private static int dp(Activity activity, int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }
}
