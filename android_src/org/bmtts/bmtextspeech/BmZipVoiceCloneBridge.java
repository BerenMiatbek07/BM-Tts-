package org.bmtts.bmtextspeech;

import android.app.Activity;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;

import com.k2fsa.sherpa.onnx.GeneratedAudio;
import com.k2fsa.sherpa.onnx.GenerationConfig;
import com.k2fsa.sherpa.onnx.OfflineTts;
import com.k2fsa.sherpa.onnx.OfflineTtsConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig;
import com.k2fsa.sherpa.onnx.OfflineTtsZipVoiceModelConfig;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;

/** Real, on-device zero-shot voice cloning backed by sherpa-onnx ZipVoice. */
public final class BmZipVoiceCloneBridge {
    private static final String TAG = "BMZipVoiceClone";
    private OfflineTts tts;
    private final String modelDirectory;

    public BmZipVoiceCloneBridge(Activity activity, String directory, int numThreads)
            throws IOException {
        if (activity == null) throw new IOException("Android activity is null");
        File root = new File(directory);
        if (!root.isDirectory()) throw new IOException("Clone model directory is missing");
        File encoder = require(root, "encoder.int8.onnx");
        File decoder = require(root, "decoder.int8.onnx");
        File vocoder = require(root, "vocos_24khz.onnx");
        File tokens = require(root, "tokens.txt");
        File lexicon = require(root, "lexicon.txt");
        File dataDir = new File(root, "espeak-ng-data");
        if (!dataDir.isDirectory()) throw new IOException("ZipVoice data directory is missing");

        OfflineTtsZipVoiceModelConfig zipvoice = new OfflineTtsZipVoiceModelConfig();
        zipvoice.setEncoder(encoder.getAbsolutePath());
        zipvoice.setDecoder(decoder.getAbsolutePath());
        zipvoice.setVocoder(vocoder.getAbsolutePath());
        zipvoice.setTokens(tokens.getAbsolutePath());
        zipvoice.setLexicon(lexicon.getAbsolutePath());
        zipvoice.setDataDir(dataDir.getAbsolutePath());

        int threads = Math.max(1, Math.min(4, numThreads));
        for (String abi : Build.SUPPORTED_ABIS) {
            if (abi != null && abi.toLowerCase().startsWith("x86")) {
                threads = 1;
                break;
            }
        }
        OfflineTtsModelConfig model = new OfflineTtsModelConfig();
        model.setZipvoice(zipvoice);
        model.setNumThreads(threads);
        model.setDebug(false);
        model.setProvider("cpu");
        OfflineTtsConfig config = new OfflineTtsConfig();
        config.setModel(model);
        config.setMaxNumSentences(1);
        config.setSilenceScale(0.2f);

        long started = SystemClock.elapsedRealtime();
        Log.i(TAG, "LOAD_BEGIN:dir=" + root.getAbsolutePath() + ":threads=" + threads);
        tts = new OfflineTts(null, config);
        if (tts.sampleRate() <= 0) {
            release();
            throw new IOException("ZipVoice returned an invalid sample rate");
        }
        modelDirectory = root.getCanonicalPath();
        Log.i(TAG, "LOAD_OK:ms=" + (SystemClock.elapsedRealtime() - started));
    }

    public boolean matches(String directory) {
        try {
            return modelDirectory.equals(new File(directory).getCanonicalPath());
        } catch (IOException error) {
            return false;
        }
    }

    public synchronized boolean synthesizeToWave(
            String text,
            String referenceWavePath,
            String referenceText,
            float speed,
            String outputPath
    ) throws IOException {
        if (tts == null) throw new IOException("ZipVoice engine was released");
        if (text == null || text.trim().isEmpty()) throw new IOException("Text is empty");
        if (referenceText == null || referenceText.trim().isEmpty()) {
            throw new IOException("Reference transcript is empty");
        }
        BmVoiceConsentBridge.WavData reference =
                BmVoiceConsentBridge.readPcm16Wave(referenceWavePath, 15);
        GenerationConfig generation = new GenerationConfig();
        generation.setReferenceAudio(reference.samples);
        generation.setReferenceSampleRate(reference.sampleRate);
        generation.setReferenceText(referenceText.trim());
        generation.setNumSteps(4);
        generation.setSpeed(Math.max(0.5f, Math.min(2.0f, speed)));
        generation.setSilenceScale(0.2f);
        generation.setExtra(new HashMap<String, String>());
        generation.getExtra().put("min_char_in_sentence", "30");

        long started = SystemClock.elapsedRealtime();
        Log.i(TAG, "GENERATE_BEGIN:chars=" + text.length()
                + ":reference_samples=" + reference.samples.length);
        GeneratedAudio audio = tts.generateWithConfig(text.trim(), generation);
        int samples = audio == null || audio.getSamples() == null
                ? 0 : audio.getSamples().length;
        Log.i(TAG, "GENERATE_OK:ms=" + (SystemClock.elapsedRealtime() - started)
                + ":samples=" + samples);
        if (samples <= 0) throw new IOException("ZipVoice produced empty audio");
        File output = new File(outputPath);
        File parent = output.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IOException("Could not create clone output directory");
        }
        output.delete();
        if (!audio.save(output.getAbsolutePath())) {
            throw new IOException("ZipVoice could not save WAV output");
        }
        return output.isFile() && output.length() > 44L;
    }

    public synchronized void release() {
        if (tts != null) {
            try { tts.release(); } catch (Throwable ignored) {}
            tts = null;
        }
    }

    private static File require(File root, String name) throws IOException {
        File file = new File(root, name);
        if (!file.isFile() || file.length() <= 0L) {
            throw new IOException("Missing ZipVoice file: " + name);
        }
        return file;
    }
}
