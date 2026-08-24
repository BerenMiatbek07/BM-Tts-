package org.bmtts.bmtextspeech;

import android.app.Activity;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Arrays;

/**
 * Test-APK-only end-to-end smoke test for downloaded Piper voices.
 *
 * The activity is exported only in a Google-test-ads APK. It downloads the
 * official model archive, uses the same BmAdMobBridge entrypoints as PyJNIus,
 * generates a WAV and leaves the verified result in external app storage so
 * an ADB test can inspect and play it.
 */
public final class BmSherpaSelfTestActivity extends Activity {
    private static final String TAG = "BMSherpaSelfTest";
    private static final int BUFFER_SIZE = 256 * 1024;
    private TextView statusView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        statusView = new TextView(this);
        statusView.setTextSize(18f);
        statusView.setPadding(32, 32, 32, 32);
        statusView.setText("Sherpa/Piper voice self-test is starting...");
        setContentView(statusView);
        logPythonBundleProbe();

        if (!isTestApk()) {
            fail("SELF_TEST_DISABLED_IN_PRODUCTION", null);
            return;
        }
        String bridgeProbe = BmPythonActivity.bridgePackagingProbe();
        Log.i(TAG, bridgeProbe);
        String runtimeProbe = BmSherpaTtsBridge.runtimeProbe(this);
        Log.i(TAG, runtimeProbe);
        if (!runtimeProbe.startsWith("SHERPA_RUNTIME_OK")) {
            fail(runtimeProbe, null);
            return;
        }
        if (getIntent().getBooleanExtra("runtime_only", false)) {
            showAndLog("RUNTIME_SELF_TEST_OK");
            return;
        }

        final String cloneModelDir = getIntent().getStringExtra("clone_model_dir");
        if (cloneModelDir != null && !cloneModelDir.trim().isEmpty()) {
            final String referenceWave = getIntent().getStringExtra("clone_reference_wave");
            final String referenceText = getIntent().getStringExtra("clone_reference_text");
            final String targetText = getIntent().getStringExtra("clone_target_text");
            new Thread(
                    () -> runCloneSelfTest(
                            cloneModelDir,
                            referenceWave,
                            referenceText,
                            targetText
                    ),
                    "bm-zipvoice-self-test"
            ).start();
            return;
        }

        final String modelId = getIntent().getStringExtra("model_id");
        String requestedUrl = getIntent().getStringExtra("model_url");
        final String modelUrl = requestedUrl == null || requestedUrl.trim().isEmpty()
                ? officialModelUrl(modelId)
                : requestedUrl;
        if (modelId == null || !modelId.matches("[A-Za-z0-9_-]+")) {
            fail("invalid-model-id", null);
            return;
        }
        if (modelUrl == null || !modelUrl.startsWith("https://")) {
            fail("invalid-model-url", null);
            return;
        }
        new Thread(
                () -> runSelfTest(modelId, modelUrl),
                "bm-sherpa-self-test"
        ).start();
    }

    private boolean isTestApk() {
        try {
            ApplicationInfo info = getPackageManager().getApplicationInfo(
                    getPackageName(),
                    PackageManager.GET_META_DATA
            );
            if (info.metaData == null) {
                return false;
            }
            Object value = info.metaData.get("BM_USE_TEST_ADS");
            return Boolean.TRUE.equals(value)
                    || "true".equalsIgnoreCase(String.valueOf(value));
        } catch (Throwable error) {
            Log.e(TAG, "SELF_TEST_METADATA_ERROR", error);
            return false;
        }
    }

    private void runCloneSelfTest(
            String modelDir,
            String referenceWave,
            String referenceText,
            String requestedText
    ) {
        File external = getExternalFilesDir("voice-clone-self-test");
        File base = external == null ? getCacheDir() : external;
        if (!base.isDirectory() && !base.mkdirs()) {
            fail("CLONE_SELF_TEST_MKDIR_FAILED", null);
            return;
        }
        File output = new File(base, "clone_preview.wav");
        output.delete();
        BmZipVoiceCloneBridge bridge = null;
        try {
            if (referenceWave == null || referenceText == null
                    || referenceText.trim().isEmpty()) {
                throw new IllegalArgumentException("clone-reference-missing");
            }
            String text = requestedText == null || requestedText.trim().isEmpty()
                    ? "The verified cloned voice is working correctly on this phone."
                    : requestedText;
            bridge = new BmZipVoiceCloneBridge(this, modelDir, 2);
            boolean ok = bridge.synthesizeToWave(
                    text,
                    referenceWave,
                    referenceText,
                    1.0f,
                    output.getAbsolutePath()
            );
            long bytes = output.isFile() ? output.length() : 0L;
            if (!ok || bytes <= 44L || !hasWaveHeader(output)) {
                throw new IllegalStateException("invalid-clone-wav:" + bytes);
            }
            showAndLog("CLONE_SELF_TEST_OK:wav=" + bytes
                    + ":path=" + output.getAbsolutePath());
        } catch (Throwable error) {
            fail("CLONE_SELF_TEST", error);
        } finally {
            if (bridge != null) bridge.release();
        }
    }

    private void runSelfTest(String modelId, String modelUrl) {
        File external = getExternalFilesDir("voice-self-test");
        File base = external == null ? getCacheDir() : external;
        File root = new File(base, modelId);
        deleteRecursively(root);
        if (!root.mkdirs() && !root.isDirectory()) {
            fail(modelId + ":mkdir-failed", null);
            return;
        }
        File archive = new File(root, modelId + ".tar.bz2");
        File modelDir = new File(root, "model");
        File output = new File(root, "preview.wav");
        try {
            long bytes = download(modelUrl, archive, modelId);
            if (bytes < 1024 * 1024) {
                throw new IllegalStateException("archive-too-small:" + bytes);
            }
            if (!modelDir.mkdirs() && !modelDir.isDirectory()) {
                throw new IllegalStateException("model-dir-create-failed");
            }
            BmAdMobBridge.extractTarBz2(
                    archive.getAbsolutePath(),
                    modelDir.getAbsolutePath()
            );
            boolean ok = BmAdMobBridge.synthesizeSherpaToWave(
                    this,
                    modelDir.getAbsolutePath(),
                    2,
                    "\u0421\u04d9\u043b\u0435\u043c! \u0411\u04b1\u043b \u049b\u0430\u0437\u0430\u049b \u0442\u0456\u043b\u0456\u043d\u0434\u0435\u0433\u0456 \u0434\u0430\u0443\u044b\u0441 \u0441\u044b\u043d\u0430\u0493\u044b.",
                    0,
                    1.0f,
                    output.getAbsolutePath()
            );
            long wavBytes = output.isFile() ? output.length() : 0L;
            if (!ok || wavBytes <= 44L || !hasWaveHeader(output)) {
                throw new IllegalStateException("invalid-wav:" + wavBytes);
            }
            String marker = "VOICE_SELF_TEST_OK:" + modelId
                    + ":wav=" + wavBytes
                    + ":path=" + output.getAbsolutePath();
            showAndLog(marker);
        } catch (Throwable error) {
            fail(modelId, error);
        } finally {
            BmAdMobBridge.releaseSherpa();
            archive.delete();
        }
    }

    private static String officialModelUrl(String modelId) {
        if (modelId == null) {
            return null;
        }
        if ("vits-piper-kk_KZ-iseke-x_low".equals(modelId)
                || "vits-piper-kk_KZ-raya-x_low".equals(modelId)) {
            return "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
                    + modelId + ".tar.bz2";
        }
        return null;
    }

    private void logPythonBundleProbe() {
        File inputDir = new File(
                getFilesDir(),
                "app/_python_bundle/site-packages/kivy/input"
        );
        File initFile = new File(inputDir, "__init__.pyc");
        String[] names = inputDir.list();
        if (names != null) {
            Arrays.sort(names);
        }
        Log.i(TAG, "PYTHON_BUNDLE_PROBE:path=" + inputDir.getAbsolutePath()
                + ":exists=" + inputDir.exists()
                + ":directory=" + inputDir.isDirectory()
                + ":read=" + inputDir.canRead()
                + ":execute=" + inputDir.canExecute()
                + ":children=" + (names == null ? "null" : Arrays.toString(names))
                + ":init_exists=" + initFile.isFile()
                + ":init_bytes=" + (initFile.isFile() ? initFile.length() : -1));
    }

    private long download(String address, File destination, String modelId)
            throws Exception {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(address).openConnection();
            connection.setInstanceFollowRedirects(true);
            connection.setConnectTimeout(20000);
            connection.setReadTimeout(120000);
            connection.setRequestProperty(
                    "User-Agent",
                    "BM-Text-to-Voice/5.6.2-device-test"
            );
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.connect();
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new IllegalStateException("HTTP-" + code);
            }
            long expected = connection.getContentLengthLong();
            long total = 0L;
            long nextLog = 4L * 1024L * 1024L;
            byte[] buffer = new byte[BUFFER_SIZE];
            try (
                    InputStream raw = connection.getInputStream();
                    BufferedInputStream input = new BufferedInputStream(raw, BUFFER_SIZE);
                    BufferedOutputStream output = new BufferedOutputStream(
                            new FileOutputStream(destination), BUFFER_SIZE)
            ) {
                int read;
                while ((read = input.read(buffer)) != -1) {
                    output.write(buffer, 0, read);
                    total += read;
                    if (total >= nextLog) {
                        Log.i(TAG, "VOICE_SELF_TEST_DOWNLOAD:" + modelId
                                + ":" + total + "/" + expected);
                        nextLog += 4L * 1024L * 1024L;
                    }
                }
                output.flush();
            }
            if (expected > 0L && total != expected) {
                throw new IllegalStateException(
                        "incomplete-download:" + total + "/" + expected
                );
            }
            return total;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private static boolean hasWaveHeader(File file) {
        try (InputStream input = new BufferedInputStream(
                new java.io.FileInputStream(file))) {
            byte[] header = new byte[12];
            if (input.read(header) != header.length) {
                return false;
            }
            return header[0] == 'R' && header[1] == 'I'
                    && header[2] == 'F' && header[3] == 'F'
                    && header[8] == 'W' && header[9] == 'A'
                    && header[10] == 'V' && header[11] == 'E';
        } catch (Throwable ignored) {
            return false;
        }
    }

    private void fail(String context, Throwable error) {
        String detail = context;
        if (error != null) {
            String message = error.getMessage();
            if (message == null || message.trim().isEmpty()) {
                message = error.getClass().getName();
            }
            detail += ":" + error.getClass().getName() + ":" + message;
            Log.e(TAG, "VOICE_SELF_TEST_ERROR:" + detail, error);
        } else {
            Log.e(TAG, "VOICE_SELF_TEST_ERROR:" + detail);
        }
        show("VOICE_SELF_TEST_ERROR:" + detail);
    }

    private void showAndLog(String text) {
        Log.i(TAG, text);
        show(text);
    }

    private void show(String text) {
        runOnUiThread(() -> statusView.setText(text));
    }

    private static void deleteRecursively(File file) {
        if (file == null || !file.exists()) {
            return;
        }
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursively(child);
                }
            }
        }
        file.delete();
    }
}
