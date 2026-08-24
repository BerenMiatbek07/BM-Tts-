package org.bmtts.bmtextspeech;

import android.app.Activity;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;

import com.k2fsa.sherpa.onnx.GeneratedAudio;
import com.k2fsa.sherpa.onnx.OfflineTts;
import com.k2fsa.sherpa.onnx.OfflineTtsConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/** Keeps one downloaded Piper model loaded while Python generates WAV chunks. */
public final class BmSherpaTtsBridge {
    private static final String TAG = "BMSherpaTts";
    private OfflineTts tts;
    private final int sampleRate;
    private final int numSpeakers;

    public BmSherpaTtsBridge(Activity activity, String modelDirectory, int numThreads)
            throws IOException {
        if (activity == null) {
            throw new IOException("Android activity is null");
        }
        File root = new File(modelDirectory);
        if (!root.isDirectory()) {
            throw new IOException("Model directory does not exist: " + modelDirectory);
        }

        File model = findLargest(root, ".onnx");
        File tokens = findNamed(root, "tokens.txt");
        if (model == null || tokens == null) {
            throw new IOException("Model .onnx or tokens.txt is missing");
        }

        File lexicon = findNamed(root, "lexicon.txt");
        File dataDir = findDirectory(root, "espeak-ng-data");
        File dictDir = findDirectory(root, "dict");

        OfflineTtsVitsModelConfig vits = new OfflineTtsVitsModelConfig();
        vits.setModel(model.getAbsolutePath());
        vits.setTokens(tokens.getAbsolutePath());
        vits.setLexicon(lexicon == null ? "" : lexicon.getAbsolutePath());
        vits.setDataDir(dataDir == null ? "" : dataDir.getAbsolutePath());
        vits.setDictDir(dictDir == null ? "" : dictDir.getAbsolutePath());
        vits.setNoiseScale(0.667f);
        vits.setNoiseScaleW(0.8f);
        vits.setLengthScale(1.0f);

        OfflineTtsModelConfig modelConfig = new OfflineTtsModelConfig();
        modelConfig.setVits(vits);
        int safeThreads = Math.max(1, Math.min(6, numThreads));
        // BlueStacks exposes an x86 host but runs this arm64-only Sherpa JNI
        // through binary translation. More than one ONNX worker can stall in
        // that environment. Real ARM phones keep the requested thread count.
        for (String abi : Build.SUPPORTED_ABIS) {
            if (abi != null && abi.toLowerCase().startsWith("x86")) {
                safeThreads = 1;
                break;
            }
        }
        modelConfig.setNumThreads(safeThreads);
        modelConfig.setDebug(false);
        modelConfig.setProvider("cpu");

        OfflineTtsConfig config = new OfflineTtsConfig();
        config.setModel(modelConfig);
        config.setRuleFsts(joinPaths(findBySuffix(root, ".fst")));
        config.setRuleFars(joinPaths(findBySuffix(root, ".far")));
        config.setMaxNumSentences(2);
        config.setSilenceScale(0.2f);

        // Downloaded voices live in app storage and every configured path is
        // absolute. Passing an Android AssetManager here makes sherpa-onnx
        // treat those paths as packaged assets and abort the whole process.
        // A null AssetManager is required for files loaded from app/SD storage.
        long loadStarted = SystemClock.elapsedRealtime();
        Log.i(TAG, "LOAD_BEGIN:model=" + model.getAbsolutePath()
                + ":threads=" + safeThreads);
        tts = new OfflineTts(null, config);
        Log.i(TAG, "LOAD_OK:ms="
                + (SystemClock.elapsedRealtime() - loadStarted));
        sampleRate = tts.sampleRate();
        numSpeakers = tts.numSpeakers();
        if (sampleRate <= 0) {
            release();
            throw new IOException("Sherpa returned an invalid sample rate");
        }
    }

    /** Verify Java/Kotlin/JNI packaging before a model download starts. */
    public static String runtimeProbe(Activity activity) {
        if (activity == null) {
            return "SHERPA_RUNTIME_ERROR:activity-null";
        }
        try {
            ClassLoader loader = activity.getClassLoader();
            Class.forName("kotlin.jvm.internal.Intrinsics", true, loader);
            Class.forName("com.k2fsa.sherpa.onnx.OfflineTtsConfig", true, loader);
            // Initializing OfflineTts loads libsherpa-onnx-jni.so.
            Class.forName("com.k2fsa.sherpa.onnx.OfflineTts", true, loader);
            return "SHERPA_RUNTIME_OK";
        } catch (Throwable error) {
            String message = error.getMessage();
            if (message == null || message.trim().isEmpty()) {
                message = error.getClass().getName();
            }
            return "SHERPA_RUNTIME_ERROR:" + error.getClass().getName() + ":" + message;
        }
    }

    public synchronized boolean synthesizeToWave(
            String text,
            int speakerId,
            float speed,
            String outputPath
    ) throws IOException {
        if (tts == null) {
            throw new IOException("Sherpa engine was released");
        }
        if (text == null || text.trim().isEmpty()) {
            throw new IOException("Text is empty");
        }
        int sid = Math.max(0, speakerId);
        if (numSpeakers > 0) {
            sid = Math.min(sid, numSpeakers - 1);
        }
        float safeSpeed = Math.max(0.5f, Math.min(2.0f, speed));
        long generateStarted = SystemClock.elapsedRealtime();
        Log.i(TAG, "GENERATE_BEGIN:chars=" + text.length()
                + ":speaker=" + sid + ":speed=" + safeSpeed);
        GeneratedAudio audio = tts.generate(text, sid, safeSpeed);
        Log.i(TAG, "GENERATE_OK:ms="
                + (SystemClock.elapsedRealtime() - generateStarted)
                + ":samples="
                + (audio == null || audio.getSamples() == null
                ? 0 : audio.getSamples().length));
        if (audio == null || audio.getSamples() == null || audio.getSamples().length == 0) {
            throw new IOException("Sherpa produced empty audio");
        }
        File output = new File(outputPath);
        File parent = output.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("Could not create output directory");
        }
        if (!audio.save(output.getAbsolutePath())) {
            throw new IOException("Sherpa could not save WAV output");
        }
        Log.i(TAG, "SAVE_OK:path=" + output.getAbsolutePath()
                + ":bytes=" + output.length());
        return output.isFile() && output.length() > 44;
    }

    public int sampleRate() {
        return sampleRate;
    }

    public int numSpeakers() {
        return numSpeakers;
    }

    public synchronized void release() {
        if (tts != null) {
            try {
                tts.release();
            } catch (Throwable ignored) {
                // no-op
            }
            tts = null;
        }
    }

    private static File findNamed(File root, String name) {
        if (root.getName().equals(name)) {
            return root;
        }
        File[] children = root.listFiles();
        if (children == null) {
            return null;
        }
        for (File child : children) {
            if (child.isFile() && child.getName().equals(name)) {
                return child;
            }
        }
        for (File child : children) {
            if (child.isDirectory()) {
                File found = findNamed(child, name);
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }

    private static File findDirectory(File root, String name) {
        if (root.isDirectory() && root.getName().equals(name)) {
            return root;
        }
        File[] children = root.listFiles();
        if (children == null) {
            return null;
        }
        for (File child : children) {
            if (child.isDirectory()) {
                if (child.getName().equals(name)) {
                    return child;
                }
                File found = findDirectory(child, name);
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }

    private static File findLargest(File root, String suffix) {
        List<File> files = findBySuffix(root, suffix);
        if (files.isEmpty()) {
            return null;
        }
        return Collections.max(files, new Comparator<File>() {
            @Override
            public int compare(File left, File right) {
                return Long.compare(left.length(), right.length());
            }
        });
    }

    private static List<File> findBySuffix(File root, String suffix) {
        List<File> result = new ArrayList<>();
        collectBySuffix(root, suffix, result);
        Collections.sort(result, new Comparator<File>() {
            @Override
            public int compare(File left, File right) {
                return left.getAbsolutePath().compareTo(right.getAbsolutePath());
            }
        });
        return result;
    }

    private static void collectBySuffix(File root, String suffix, List<File> result) {
        File[] children = root.listFiles();
        if (children == null) {
            return;
        }
        for (File child : children) {
            if (child.isDirectory()) {
                collectBySuffix(child, suffix, result);
            } else if (child.getName().toLowerCase().endsWith(suffix)) {
                result.add(child);
            }
        }
    }

    private static String joinPaths(List<File> files) {
        StringBuilder builder = new StringBuilder();
        for (File file : files) {
            if (builder.length() > 0) {
                builder.append(',');
            }
            builder.append(file.getAbsolutePath());
        }
        return builder.toString();
    }
}
