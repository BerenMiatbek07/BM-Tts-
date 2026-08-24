package org.bmtts.bmtextspeech;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Native microphone and WAV bridge for voice-clone consent.
 *
 * The retired offline speaker/ASR verification pack intentionally is not used
 * here. This bridge only captures app-owned live microphone audio and provides
 * the bounded PCM reader shared by the ZipVoice engine.
 */
public final class BmVoiceConsentBridge {
    private static final String TAG = "BMVoiceConsent";
    private static final int SAMPLE_RATE = 16000;
    private static final Object RECORD_LOCK = new Object();
    private static final AtomicBoolean STOP_REQUESTED = new AtomicBoolean(false);

    private static volatile AudioRecord recorder;
    private static volatile Thread recorderThread;
    private static volatile String recordingState = "idle";
    private static volatile String recordingError = "";
    private static volatile String recordingPath = "";
    private static volatile long recordedSamples = 0L;

    private BmVoiceConsentBridge() {}

    public static String startLiveRecording(final Activity activity, int maxSeconds) {
        return startRecording(activity, Math.min(15, maxSeconds), "live");
    }

    public static String startReferenceRecording(final Activity activity, int maxSeconds) {
        return startRecording(activity, Math.min(30, maxSeconds), "reference");
    }

    private static String startRecording(
            final Activity activity,
            int maxSeconds,
            final String purpose
    ) {
        if (activity == null) {
            return errorJson("activity_missing");
        }
        if (Build.VERSION.SDK_INT >= 23
                && activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            return errorJson("microphone_permission_required");
        }
        final int limit = Math.max(2, maxSeconds);
        synchronized (RECORD_LOCK) {
            if (recorderThread != null && recorderThread.isAlive()) {
                return errorJson("recording_already_active");
            }
            File directory = new File(activity.getCacheDir(), "voice_consent");
            if (!directory.isDirectory() && !directory.mkdirs()) {
                return errorJson("cache_directory_failed");
            }
            File output = new File(directory, purpose + "_" + UUID.randomUUID() + ".wav");
            recordingPath = output.getAbsolutePath();
            recordingError = "";
            recordedSamples = 0L;
            recordingState = "starting";
            STOP_REQUESTED.set(false);
            recorderThread = new Thread(new Runnable() {
                @Override
                public void run() {
                    recordMicrophone(output, limit);
                }
            }, "BM-voice-consent-mic");
            recorderThread.start();
            return statusJson();
        }
    }

    public static String stopLiveRecording() {
        STOP_REQUESTED.set(true);
        AudioRecord current = recorder;
        if (current != null) {
            try {
                current.stop();
            } catch (Throwable ignored) {
            }
        }
        return statusJson();
    }

    public static String liveRecordingStatus() {
        return statusJson();
    }

    public static String inspectConsentWave(String path, int maximumSeconds) {
        try {
            WavData audio = readPcm16Wave(path, Math.max(1, Math.min(30, maximumSeconds)));
            return "{\"ok\":true,\"path\":\"" + jsonEscape(path)
                    + "\",\"duration_seconds\":"
                    + String.format(Locale.US, "%.3f", audio.seconds()) + "}";
        } catch (Throwable error) {
            return errorJson(safeCode(error));
        }
    }

    private static void recordMicrophone(File output, int maxSeconds) {
        File raw = new File(output.getAbsolutePath() + ".pcm.tmp");
        int minimum = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
        );
        if (minimum <= 0) {
            finishRecording("failed", "unsupported_audio_config", raw);
            return;
        }
        int bufferBytes = Math.max(minimum * 2, 4096);
        AudioRecord local = null;
        BufferedOutputStream stream = null;
        try {
            // MIC is intentional: the verification recording cannot be selected
            // from storage or supplied through the file-picker path.
            local = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferBytes
            );
            if (local.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new IOException("microphone_initialization_failed");
            }
            recorder = local;
            stream = new BufferedOutputStream(new FileOutputStream(raw));
            byte[] buffer = new byte[bufferBytes];
            long maximumSamples = (long) SAMPLE_RATE * maxSeconds;
            local.startRecording();
            recordingState = "recording";
            while (!STOP_REQUESTED.get() && recordedSamples < maximumSamples) {
                int wanted = (int) Math.min(buffer.length, (maximumSamples - recordedSamples) * 2L);
                int count = local.read(buffer, 0, wanted);
                if (count > 0) {
                    stream.write(buffer, 0, count);
                    recordedSamples += count / 2L;
                } else if (count < 0) {
                    throw new IOException("microphone_read_failed_" + count);
                }
            }
            stream.flush();
            stream.close();
            stream = null;
            if (recordedSamples <= SAMPLE_RATE) {
                throw new IOException("live_audio_too_short");
            }
            writeWaveFromPcm(raw, output, SAMPLE_RATE, 1);
            if (!output.isFile() || output.length() <= 44L) {
                throw new IOException("live_wave_invalid");
            }
            finishRecording("ready", "", raw);
        } catch (Throwable error) {
            Log.e(TAG, "Live microphone recording failed", error);
            finishRecording("failed", safeCode(error), raw);
            if (output.isFile()) {
                output.delete();
            }
        } finally {
            if (stream != null) {
                try { stream.close(); } catch (Throwable ignored) {}
            }
            if (local != null) {
                try { local.stop(); } catch (Throwable ignored) {}
                try { local.release(); } catch (Throwable ignored) {}
            }
            recorder = null;
            recorderThread = null;
        }
    }

    private static void finishRecording(String state, String error, File raw) {
        recordingState = state;
        recordingError = error == null ? "" : error;
        if (raw != null && raw.isFile()) {
            raw.delete();
        }
    }

    public static boolean deleteConsentAudio(String path, Activity activity) {
        if (path == null || activity == null) {
            return false;
        }
        try {
            File allowed = new File(activity.getCacheDir(), "voice_consent").getCanonicalFile();
            File target = new File(path).getCanonicalFile();
            if (!target.getPath().startsWith(allowed.getPath() + File.separator)) {
                return false;
            }
            return !target.exists() || target.delete();
        } catch (Throwable error) {
            return false;
        }
    }

    static WavData readPcm16Wave(String path, int maximumSeconds) throws IOException {
        File file = requireFile(path, "wave_missing");
        BufferedInputStream input = new BufferedInputStream(new FileInputStream(file));
        try {
            byte[] riff = readExactly(input, 12);
            if (!ascii(riff, 0, 4).equals("RIFF") || !ascii(riff, 8, 4).equals("WAVE")) {
                throw new IOException("wave_format_required");
            }
            int channels = 0;
            int sampleRate = 0;
            int bits = 0;
            int audioFormat = 0;
            byte[] data = null;
            while (true) {
                byte[] header = readMaybe(input, 8);
                if (header == null) break;
                String id = ascii(header, 0, 4);
                int size = intLe(header, 4);
                if (size < 0 || size > 512 * 1024 * 1024) {
                    throw new IOException("wave_chunk_invalid");
                }
                if (id.equals("fmt ")) {
                    byte[] format = readExactly(input, size);
                    if (size < 16) throw new IOException("wave_fmt_invalid");
                    audioFormat = shortLe(format, 0);
                    channels = shortLe(format, 2);
                    sampleRate = intLe(format, 4);
                    bits = shortLe(format, 14);
                } else if (id.equals("data")) {
                    int maximumBytes = SAMPLE_RATE * Math.max(1, maximumSeconds) * 2 * 2;
                    if (size > maximumBytes * 4) throw new IOException("wave_too_long");
                    data = readExactly(input, size);
                } else {
                    skipExactly(input, size);
                }
                if ((size & 1) != 0) skipExactly(input, 1);
                if (data != null && sampleRate > 0) break;
            }
            if (audioFormat != 1 || bits != 16 || channels < 1 || channels > 2
                    || sampleRate < 8000 || sampleRate > 96000 || data == null) {
                throw new IOException("pcm16_wave_required");
            }
            int frames = data.length / (channels * 2);
            if (frames <= 0) throw new IOException("wave_empty");
            float[] mono = new float[frames];
            for (int frame = 0; frame < frames; frame++) {
                int sum = 0;
                for (int channel = 0; channel < channels; channel++) {
                    int offset = (frame * channels + channel) * 2;
                    sum += (short) ((data[offset] & 0xff) | (data[offset + 1] << 8));
                }
                mono[frame] = (sum / (float) channels) / 32768.0f;
            }
            float[] samples = sampleRate == SAMPLE_RATE ? mono : resampleLinear(mono, sampleRate, SAMPLE_RATE);
            if (samples.length > SAMPLE_RATE * maximumSeconds) {
                throw new IOException("wave_too_long");
            }
            return new WavData(samples, SAMPLE_RATE);
        } finally {
            input.close();
        }
    }

    private static float[] resampleLinear(float[] input, int fromRate, int toRate) {
        int outputLength = Math.max(1, (int) Math.round(input.length * (toRate / (double) fromRate)));
        float[] output = new float[outputLength];
        double scale = fromRate / (double) toRate;
        for (int index = 0; index < outputLength; index++) {
            double position = index * scale;
            int left = Math.min(input.length - 1, (int) position);
            int right = Math.min(input.length - 1, left + 1);
            double fraction = position - left;
            output[index] = (float) (input[left] * (1.0 - fraction) + input[right] * fraction);
        }
        return output;
    }

    private static String statusJson() {
        return "{"
                + "\"ok\":" + (!"failed".equals(recordingState)) + ","
                + "\"state\":\"" + jsonEscape(recordingState) + "\","
                + "\"error\":\"" + jsonEscape(recordingError) + "\","
                + "\"path\":\"" + jsonEscape(recordingPath) + "\","
                + "\"duration_seconds\":"
                + String.format(Locale.US, "%.3f", recordedSamples / (double) SAMPLE_RATE)
                + "}";
    }

    private static String errorJson(String code) {
        return "{\"ok\":false,\"state\":\"failed\",\"error\":\""
                + jsonEscape(code) + "\"}";
    }

    private static String safeCode(Throwable error) {
        String value = error == null ? "unknown_error" : error.getMessage();
        if (value == null || value.trim().isEmpty()) value = "unknown_error";
        return value.replaceAll("[^a-zA-Z0-9_.-]", "_");
    }

    private static String jsonEscape(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    private static File requireFile(String path, String code) throws IOException {
        File file = path == null ? null : new File(path);
        if (file == null || !file.isFile() || file.length() <= 0L) {
            throw new IOException(code);
        }
        return file;
    }

    private static void writeWaveFromPcm(File pcm, File wave, int sampleRate, int channels)
            throws IOException {
        long dataLength = pcm.length();
        if (dataLength <= 0 || dataLength > Integer.MAX_VALUE - 44L) {
            throw new IOException("pcm_invalid");
        }
        BufferedInputStream source = new BufferedInputStream(new FileInputStream(pcm));
        BufferedOutputStream destination = new BufferedOutputStream(new FileOutputStream(wave));
        try {
            destination.write(new byte[]{'R','I','F','F'});
            writeIntLe(destination, (int) dataLength + 36);
            destination.write(new byte[]{'W','A','V','E','f','m','t',' '});
            writeIntLe(destination, 16);
            writeShortLe(destination, 1);
            writeShortLe(destination, channels);
            writeIntLe(destination, sampleRate);
            writeIntLe(destination, sampleRate * channels * 2);
            writeShortLe(destination, channels * 2);
            writeShortLe(destination, 16);
            destination.write(new byte[]{'d','a','t','a'});
            writeIntLe(destination, (int) dataLength);
            byte[] buffer = new byte[32768];
            int count;
            while ((count = source.read(buffer)) >= 0) {
                if (count > 0) destination.write(buffer, 0, count);
            }
            destination.flush();
        } finally {
            try { source.close(); } finally { destination.close(); }
        }
    }

    private static void writeIntLe(BufferedOutputStream out, int value) throws IOException {
        out.write(value & 0xff); out.write((value >>> 8) & 0xff);
        out.write((value >>> 16) & 0xff); out.write((value >>> 24) & 0xff);
    }

    private static void writeShortLe(BufferedOutputStream out, int value) throws IOException {
        out.write(value & 0xff); out.write((value >>> 8) & 0xff);
    }

    private static byte[] readExactly(BufferedInputStream input, int size) throws IOException {
        byte[] output = new byte[size];
        int offset = 0;
        while (offset < size) {
            int count = input.read(output, offset, size - offset);
            if (count < 0) throw new IOException("unexpected_wave_end");
            offset += count;
        }
        return output;
    }

    private static byte[] readMaybe(BufferedInputStream input, int size) throws IOException {
        byte[] output = new byte[size];
        int first = input.read();
        if (first < 0) return null;
        output[0] = (byte) first;
        int offset = 1;
        while (offset < size) {
            int count = input.read(output, offset, size - offset);
            if (count < 0) throw new IOException("unexpected_wave_end");
            offset += count;
        }
        return output;
    }

    private static void skipExactly(BufferedInputStream input, int size) throws IOException {
        int remaining = size;
        while (remaining > 0) {
            long skipped = input.skip(remaining);
            if (skipped <= 0) {
                if (input.read() < 0) throw new IOException("unexpected_wave_end");
                skipped = 1;
            }
            remaining -= (int) skipped;
        }
    }

    private static String ascii(byte[] data, int offset, int length) {
        return new String(data, offset, length, StandardCharsets.US_ASCII);
    }

    private static int intLe(byte[] data, int offset) {
        return (data[offset] & 0xff) | ((data[offset + 1] & 0xff) << 8)
                | ((data[offset + 2] & 0xff) << 16) | ((data[offset + 3] & 0xff) << 24);
    }

    private static int shortLe(byte[] data, int offset) {
        return (data[offset] & 0xff) | ((data[offset + 1] & 0xff) << 8);
    }

    static final class WavData {
        final float[] samples;
        final int sampleRate;
        WavData(float[] samples, int sampleRate) {
            this.samples = samples;
            this.sampleRate = sampleRate;
        }
        double seconds() { return samples.length / (double) sampleRate; }
    }
}
