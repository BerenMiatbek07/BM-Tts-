package org.bmtts.bmtextspeech;

import android.Manifest;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.media.AudioFormat;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;

import org.kivy.android.PythonActivity;

/**
 * Kivy host activity. It intentionally does not add App Open ads or modify
 * Android's content root during startup. File picker results are retained for
 * the Python polling bridge.
 */
public class BmPythonActivity extends PythonActivity {
    private static final String BRIDGE_TAG = "BMBridgeProbe";
    private static final int MICROPHONE_PERMISSION_REQUEST = 7412;
    private static final Class<?>[] REQUIRED_BRIDGES = new Class<?>[]{
            BmLaunchActivity.class,
            BmAdMobBridge.class,
            BmArchiveBridge.class,
            BmSherpaTtsBridge.class,
            BmZipVoiceCloneBridge.class,
            BmVoiceConsentBridge.class,
            BmBillingBridge.class,
            BmSherpaSelfTestActivity.class
    };
    private static String pendingActivityResult = "";
    private boolean resumedAfterPause = false;
    private BmZipVoiceCloneBridge zipVoiceClone;
    private volatile String microphonePermissionState = "idle";
    private volatile boolean nativeBannersSuspendedByUi = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        super.onCreate(savedInstanceState);
        // Keep reflection-only PyJNIus bridge classes in release DEX and emit
        // a deterministic device-test marker without loading a voice model.
        Log.i(BRIDGE_TAG, bridgePackagingProbe());
        String sherpaRuntime = BmSherpaTtsBridge.runtimeProbe(this);
        if (sherpaRuntime.startsWith("SHERPA_RUNTIME_OK")) {
            Log.i(BRIDGE_TAG, sherpaRuntime);
        } else {
            Log.e(BRIDGE_TAG, sherpaRuntime);
        }
    }

    @Override
    protected void onDestroy() {
        BmBillingBridge.endConnection();
        super.onDestroy();
    }

    @Override
    protected void onPause() {
        // Native AdMob views are above SDL. Removing the overlay before SDL's
        // surface is destroyed prevents a black screen on return from an ad
        // click, browser, file picker, or another full-screen activity.
        BmAdMobBridge.setBannersSuspended(this, true);
        resumedAfterPause = true;
        super.onPause();
    }

    @Override
    protected void onResume() {
        // Re-assert portrait after returning from file pickers, browser/ad
        // activities and OEM split-screen transitions.  A number of Vivo and
        // Oppo builds otherwise restore the SDL surface with sensor rotation.
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        super.onResume();
        final BmPythonActivity activity = this;
        if (resumedAfterPause) {
            resumedAfterPause = false;
            new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
                @Override
                public void run() {
                    activity.refreshSdlSurface();
                }
            }, 220L);
        }
        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!activity.isFinishing() && !activity.isDestroyed()) {
                    BmAdMobBridge.setBannersSuspended(
                            activity,
                            activity.nativeBannersSuspendedByUi
                    );
                }
            }
        }, 700L);
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

    /**
     * Some ARM-on-x86 Android emulators recreate SDL's Surface but never
     * deliver a drawable frame after returning from Chrome/an ad. A temporary
     * one-pixel layout nudge emits surfaceChanged and restores the existing
     * Kivy canvas without restarting Python or losing the current session.
     */
    private void refreshSdlSurface() {
        try {
            View content = findViewById(android.R.id.content);
            final View surface = findSdlSurface(content);
            if (surface == null || surface.getWidth() <= 1) {
                return;
            }
            final ViewGroup.LayoutParams params = surface.getLayoutParams();
            if (params == null) {
                return;
            }
            final int originalWidth = params.width;
            params.width = surface.getWidth() - 1;
            surface.setLayoutParams(params);
            surface.requestLayout();
            new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
                @Override
                public void run() {
                    try {
                        ViewGroup.LayoutParams restored = surface.getLayoutParams();
                        restored.width = originalWidth;
                        surface.setLayoutParams(restored);
                        surface.requestLayout();
                        surface.invalidate();
                        Log.i(BRIDGE_TAG, "SDL_SURFACE_REFRESH_OK");
                    } catch (Throwable error) {
                        Log.w(BRIDGE_TAG, "SDL_SURFACE_REFRESH_RESTORE_FAILED", error);
                    }
                }
            }, 90L);
        } catch (Throwable error) {
            Log.w(BRIDGE_TAG, "SDL_SURFACE_REFRESH_FAILED", error);
        }
    }

    private static View findSdlSurface(View view) {
        if (view == null) {
            return null;
        }
        String className = view.getClass().getName();
        if (className.endsWith(".SDLSurface") || className.contains("SDLSurface")) {
            return view;
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index++) {
                View found = findSdlSurface(group.getChildAt(index));
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }

    public static String bridgePackagingProbe() {
        StringBuilder names = new StringBuilder();
        for (Class<?> bridge : REQUIRED_BRIDGES) {
            if (names.length() > 0) {
                names.append(',');
            }
            names.append(bridge.getName());
        }
        return "BRIDGES_OK:" + names;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        String uriText = "";
        int flags = 0;
        if (data != null) {
            flags = data.getFlags();
            Uri uri = data.getData();
            if (uri != null) {
                uriText = uri.toString();
                int takeFlags = flags & (
                        Intent.FLAG_GRANT_READ_URI_PERMISSION
                                | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                );
                if (takeFlags != 0) {
                    try {
                        getContentResolver().takePersistableUriPermission(uri, takeFlags);
                    } catch (Throwable ignored) {
                        // Some providers grant read access only for this process.
                    }
                }
            }
        }

        synchronized (BmPythonActivity.class) {
            pendingActivityResult = requestCode + "\n"
                    + resultCode + "\n"
                    + flags + "\n"
                    + uriText;
        }
    }

    public static synchronized String consumeActivityResult() {
        String result = pendingActivityResult;
        pendingActivityResult = "";
        return result;
    }

    public String consumePendingActivityResult() {
        return consumeActivityResult();
    }

    // PyJNIus can always access the live PythonActivity instance, while
    // resolving additional app classes by name is unreliable on a few OEM
    // Android runtimes and ARM-on-x86 emulators. Keep all Python-facing voice
    // operations on this already-loaded class and delegate internally.
    public void extractTarBz2(String archivePath, String destinationPath)
            throws java.io.IOException {
        BmArchiveBridge.extractTarBz2(archivePath, destinationPath);
    }

    public void extractTarBz2Selected(
            String archivePath,
            String destinationPath,
            String commaSeparatedBaseNames
    ) throws java.io.IOException {
        BmArchiveBridge.extractTarBz2Selected(
                archivePath, destinationPath, commaSeparatedBaseNames);
    }

    public boolean synthesizeSherpaToWave(
            String modelDirectory,
            int numThreads,
            String text,
            int speakerId,
            float speed,
            String outputPath
    ) throws java.io.IOException {
        return BmAdMobBridge.synthesizeSherpaToWave(
                this,
                modelDirectory,
                numThreads,
                text,
                speakerId,
                speed,
                outputPath
        );
    }

    public void releaseSherpa() {
        BmAdMobBridge.releaseSherpa();
    }

    public synchronized boolean synthesizeZipVoiceToWave(
            String modelDirectory,
            int numThreads,
            String text,
            String referenceWavePath,
            String referenceText,
            float speed,
            String outputPath
    ) throws IOException {
        if (zipVoiceClone == null || !zipVoiceClone.matches(modelDirectory)) {
            releaseZipVoice();
            zipVoiceClone = new BmZipVoiceCloneBridge(this, modelDirectory, numThreads);
        }
        return zipVoiceClone.synthesizeToWave(
                text, referenceWavePath, referenceText, speed, outputPath
        );
    }

    public synchronized void releaseZipVoice() {
        if (zipVoiceClone != null) {
            zipVoiceClone.release();
            zipVoiceClone = null;
        }
    }

    public String startVoiceConsentRecording(int maxSeconds) {
        return BmVoiceConsentBridge.startLiveRecording(this, maxSeconds);
    }

    public String startVoiceReferenceRecording(int maxSeconds) {
        return BmVoiceConsentBridge.startReferenceRecording(this, maxSeconds);
    }

    public String stopVoiceConsentRecording() {
        return BmVoiceConsentBridge.stopLiveRecording();
    }

    public String voiceConsentRecordingStatus() {
        return BmVoiceConsentBridge.liveRecordingStatus();
    }

    public boolean deleteVoiceConsentAudio(String path) {
        return BmVoiceConsentBridge.deleteConsentAudio(path, this);
    }

    /**
     * Decode an Edge MP3 cue to a standard 16-bit PCM WAV.  Microsoft's
     * consumer endpoint no longer returns RIFF audio for every locale, while
     * Android's platform decoder supports MP3 on every device in our minSdk
     * range.  Timecode rendering therefore downloads the reliable MP3 stream
     * and converts it locally before assembling the timeline.
     */
    public boolean transcodeMp3ToWav(String inputPath, String outputPath)
            throws IOException {
        File input = new File(inputPath);
        File output = new File(outputPath);
        File raw = new File(outputPath + ".pcm.tmp");
        if (!input.isFile() || input.length() <= 0L) {
            throw new IOException("Input MP3 is missing or empty");
        }
        File parent = output.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IOException("Could not create WAV directory");
        }
        output.delete();
        raw.delete();

        MediaExtractor extractor = new MediaExtractor();
        MediaCodec decoder = null;
        BufferedOutputStream pcmOutput = null;
        int sampleRate = 0;
        int channelCount = 0;
        int pcmEncoding = AudioFormat.ENCODING_PCM_16BIT;
        try {
            extractor.setDataSource(input.getAbsolutePath());
            int trackIndex = -1;
            MediaFormat inputFormat = null;
            for (int index = 0; index < extractor.getTrackCount(); index++) {
                MediaFormat candidate = extractor.getTrackFormat(index);
                String mime = candidate.getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("audio/")) {
                    trackIndex = index;
                    inputFormat = candidate;
                    break;
                }
            }
            if (trackIndex < 0 || inputFormat == null) {
                throw new IOException("No audio track in MP3");
            }
            extractor.selectTrack(trackIndex);
            String mime = inputFormat.getString(MediaFormat.KEY_MIME);
            if (mime == null) {
                throw new IOException("MP3 track has no MIME type");
            }
            if (inputFormat.containsKey(MediaFormat.KEY_SAMPLE_RATE)) {
                sampleRate = inputFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE);
            }
            if (inputFormat.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) {
                channelCount = inputFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
            }

            decoder = MediaCodec.createDecoderByType(mime);
            decoder.configure(inputFormat, null, null, 0);
            decoder.start();
            pcmOutput = new BufferedOutputStream(new FileOutputStream(raw));
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            boolean inputEnded = false;
            boolean outputEnded = false;
            while (!outputEnded) {
                if (!inputEnded) {
                    int inputIndex = decoder.dequeueInputBuffer(10_000L);
                    if (inputIndex >= 0) {
                        ByteBuffer buffer = decoder.getInputBuffer(inputIndex);
                        if (buffer == null) {
                            throw new IOException("Decoder input buffer unavailable");
                        }
                        buffer.clear();
                        int size = extractor.readSampleData(buffer, 0);
                        if (size < 0) {
                            decoder.queueInputBuffer(
                                    inputIndex, 0, 0, 0L,
                                    MediaCodec.BUFFER_FLAG_END_OF_STREAM
                            );
                            inputEnded = true;
                        } else {
                            decoder.queueInputBuffer(
                                    inputIndex, 0, size,
                                    Math.max(0L, extractor.getSampleTime()), 0
                            );
                            extractor.advance();
                        }
                    }
                }

                int outputIndex = decoder.dequeueOutputBuffer(info, 10_000L);
                if (outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    MediaFormat decoded = decoder.getOutputFormat();
                    if (decoded.containsKey(MediaFormat.KEY_SAMPLE_RATE)) {
                        sampleRate = decoded.getInteger(MediaFormat.KEY_SAMPLE_RATE);
                    }
                    if (decoded.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) {
                        channelCount = decoded.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
                    }
                    if (decoded.containsKey(MediaFormat.KEY_PCM_ENCODING)) {
                        pcmEncoding = decoded.getInteger(MediaFormat.KEY_PCM_ENCODING);
                    }
                } else if (outputIndex >= 0) {
                    ByteBuffer buffer = decoder.getOutputBuffer(outputIndex);
                    if (buffer != null && info.size > 0
                            && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
                        buffer.position(info.offset);
                        buffer.limit(info.offset + info.size);
                        byte[] bytes = new byte[info.size];
                        buffer.get(bytes);
                        pcmOutput.write(bytes);
                    }
                    decoder.releaseOutputBuffer(outputIndex, false);
                    if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                        outputEnded = true;
                    }
                }
            }
            pcmOutput.flush();
            pcmOutput.close();
            pcmOutput = null;

            if (sampleRate <= 0 || channelCount <= 0 || raw.length() <= 0L) {
                throw new IOException("Decoder produced no PCM audio");
            }
            if (pcmEncoding != AudioFormat.ENCODING_PCM_16BIT) {
                throw new IOException("Unsupported decoded PCM encoding: " + pcmEncoding);
            }
            writeWaveFile(raw, output, sampleRate, channelCount);
            if (!output.isFile() || output.length() <= 44L) {
                throw new IOException("Decoded WAV is empty");
            }
            return true;
        } catch (IOException error) {
            output.delete();
            throw error;
        } catch (Throwable error) {
            output.delete();
            throw new IOException("MP3 to WAV conversion failed", error);
        } finally {
            if (pcmOutput != null) {
                try {
                    pcmOutput.close();
                } catch (Throwable ignored) {
                }
            }
            if (decoder != null) {
                try {
                    decoder.stop();
                } catch (Throwable ignored) {
                }
                try {
                    decoder.release();
                } catch (Throwable ignored) {
                }
            }
            try {
                extractor.release();
            } catch (Throwable ignored) {
            }
            raw.delete();
        }
    }

    private static void writeWaveFile(
            File raw, File output, int sampleRate, int channelCount
    ) throws IOException {
        long dataSize = raw.length();
        if (dataSize > 0xffffffffL - 36L) {
            throw new IOException("Decoded cue is too large for WAV");
        }
        int byteRate = sampleRate * channelCount * 2;
        try (
                BufferedOutputStream destination =
                        new BufferedOutputStream(new FileOutputStream(output));
                BufferedInputStream source =
                        new BufferedInputStream(new FileInputStream(raw))
        ) {
            destination.write(new byte[]{'R', 'I', 'F', 'F'});
            writeIntLe(destination, (int) (36L + dataSize));
            destination.write(new byte[]{'W', 'A', 'V', 'E'});
            destination.write(new byte[]{'f', 'm', 't', ' '});
            writeIntLe(destination, 16);
            writeShortLe(destination, 1);
            writeShortLe(destination, channelCount);
            writeIntLe(destination, sampleRate);
            writeIntLe(destination, byteRate);
            writeShortLe(destination, channelCount * 2);
            writeShortLe(destination, 16);
            destination.write(new byte[]{'d', 'a', 't', 'a'});
            writeIntLe(destination, (int) dataSize);
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = source.read(buffer)) >= 0) {
                if (count > 0) {
                    destination.write(buffer, 0, count);
                }
            }
            destination.flush();
        }
    }

    private static void writeIntLe(BufferedOutputStream output, int value)
            throws IOException {
        output.write(value & 0xff);
        output.write((value >>> 8) & 0xff);
        output.write((value >>> 16) & 0xff);
        output.write((value >>> 24) & 0xff);
    }

    private static void writeShortLe(BufferedOutputStream output, int value)
            throws IOException {
        output.write(value & 0xff);
        output.write((value >>> 8) & 0xff);
    }

    public String sherpaRuntimeProbe() {
        return BmSherpaTtsBridge.runtimeProbe(this);
    }

    public void initializeAds(String appOpenId) {
        BmAdMobBridge.initialize(this, appOpenId);
    }

    public void loadAppOpenAd(String unitId) {
        BmAdMobBridge.loadAppOpenAd(this, unitId);
    }

    public void loadAndShowAppOpenAd(String unitId) {
        BmAdMobBridge.loadAndShowAppOpenAd(this, unitId);
    }

    public void loadBanner(String slot, String unitId) {
        BmAdMobBridge.loadBanner(this, slot, unitId);
    }

    public void updateBannerFrame(
            String slot,
            int x,
            int y,
            int width,
            int height,
            int windowHeight,
            boolean visible
    ) {
        BmAdMobBridge.updateBannerFrame(
                this,
                slot,
                x,
                y,
                width,
                height,
                windowHeight,
                visible
        );
    }

    /** Hide native AdMob views while a Kivy modal/picker covers the canvas. */
    public void setNativeBannersSuspended(boolean suspended) {
        nativeBannersSuspendedByUi = suspended;
        runOnUiThread(() -> BmAdMobBridge.setBannersSuspended(this, suspended));
    }

    /** Keep a large model download/install from being frozen by screen sleep. */
    public void setModelDownloadActive(boolean active) {
        runOnUiThread(() -> {
            if (active) {
                getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            } else {
                getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            }
        });
    }

    public boolean hasMicrophonePermission() {
        return android.os.Build.VERSION.SDK_INT < 23
                || checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED;
    }

    /**
     * Request microphone permission on the Android UI thread.  Python polls
     * microphonePermissionState(), so it never assumes an asynchronous
     * permission request has already completed.
     */
    public String requestMicrophonePermission() {
        if (hasMicrophonePermission()) {
            microphonePermissionState = "granted";
            return microphonePermissionState;
        }
        microphonePermissionState = "pending";
        final BmPythonActivity activity = this;
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                activity.requestPermissions(
                        new String[]{Manifest.permission.RECORD_AUDIO},
                        MICROPHONE_PERMISSION_REQUEST
                );
            }
        });
        return microphonePermissionState;
    }

    public String microphonePermissionState() {
        if (hasMicrophonePermission()) {
            microphonePermissionState = "granted";
        }
        return microphonePermissionState;
    }

    public void openApplicationSettings() {
        Intent intent = new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
        intent.setData(Uri.parse("package:" + getPackageName()));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != MICROPHONE_PERMISSION_REQUEST) {
            return;
        }
        microphonePermissionState = (
                grantResults.length > 0
                        && grantResults[0] == PackageManager.PERMISSION_GRANTED
        ) ? "granted" : "denied";
        Log.i(BRIDGE_TAG, "MICROPHONE_PERMISSION_" + microphonePermissionState.toUpperCase());
    }

    public void loadInterstitialAd(String unitId) {
        BmAdMobBridge.loadInterstitialAd(this, unitId);
    }

    public void showInterstitialAd(String unitId) {
        BmAdMobBridge.showInterstitialAd(this, unitId);
    }
}
