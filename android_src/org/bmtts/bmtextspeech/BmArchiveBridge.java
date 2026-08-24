package org.bmtts.bmtextspeech;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.compressors.bzip2.BZip2CompressorInputStream;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/** Safe extractor for official sherpa-onnx .tar.bz2 voice archives. */
public final class BmArchiveBridge {
    private static final int BUFFER_SIZE = 128 * 1024;

    private BmArchiveBridge() {
    }

    public static void extractTarBz2(String archivePath, String destinationPath)
            throws IOException {
        File archive = new File(archivePath);
        File destination = new File(destinationPath);
        if (!archive.isFile()) {
            throw new IOException("Archive does not exist: " + archivePath);
        }
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("Could not create destination: " + destinationPath);
        }

        String root = destination.getCanonicalPath() + File.separator;
        byte[] buffer = new byte[BUFFER_SIZE];

        try (
                BufferedInputStream fileInput = new BufferedInputStream(
                        new FileInputStream(archive), BUFFER_SIZE);
                BZip2CompressorInputStream bzipInput =
                        new BZip2CompressorInputStream(fileInput, true);
                TarArchiveInputStream tarInput = new TarArchiveInputStream(bzipInput)
        ) {
            TarArchiveEntry entry;
            while ((entry = tarInput.getNextTarEntry()) != null) {
                if (entry.isSymbolicLink() || entry.isLink()) {
                    throw new IOException("Archive links are not allowed: " + entry.getName());
                }

                File output = new File(destination, entry.getName());
                String canonical = output.getCanonicalPath();
                if (!canonical.startsWith(root)) {
                    throw new IOException("Unsafe archive path: " + entry.getName());
                }

                if (entry.isDirectory()) {
                    if (!output.exists() && !output.mkdirs()) {
                        throw new IOException("Could not create directory: " + output);
                    }
                    continue;
                }

                File parent = output.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("Could not create directory: " + parent);
                }

                try (BufferedOutputStream target = new BufferedOutputStream(
                        new FileOutputStream(output), BUFFER_SIZE)) {
                    int count;
                    while ((count = tarInput.read(buffer)) != -1) {
                        target.write(buffer, 0, count);
                    }
                    target.flush();
                }
            }
        }
    }

    /**
     * Extract only explicitly allowed base filenames into a flat destination.
     * Large ASR archives contain auxiliary files that the app never uses. This
     * also avoids copying the 365 MB model a second time after extraction.
     */
    public static void extractTarBz2Selected(
            String archivePath,
            String destinationPath,
            String commaSeparatedBaseNames
    ) throws IOException {
        File archive = new File(archivePath);
        File destination = new File(destinationPath);
        if (!archive.isFile()) {
            throw new IOException("Archive does not exist: " + archivePath);
        }
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("Could not create destination: " + destinationPath);
        }

        Set<String> wanted = new HashSet<>(Arrays.asList(commaSeparatedBaseNames.split(",")));
        wanted.remove("");
        if (wanted.isEmpty()) {
            throw new IOException("No archive members were requested");
        }
        Set<String> found = new HashSet<>();
        byte[] buffer = new byte[BUFFER_SIZE];

        try (
                BufferedInputStream fileInput = new BufferedInputStream(
                        new FileInputStream(archive), BUFFER_SIZE);
                BZip2CompressorInputStream bzipInput =
                        new BZip2CompressorInputStream(fileInput, true);
                TarArchiveInputStream tarInput = new TarArchiveInputStream(bzipInput)
        ) {
            TarArchiveEntry entry;
            while ((entry = tarInput.getNextTarEntry()) != null) {
                if (entry.isSymbolicLink() || entry.isLink()) {
                    throw new IOException("Archive links are not allowed: " + entry.getName());
                }
                if (!entry.isFile()) {
                    continue;
                }
                String baseName = new File(entry.getName()).getName();
                if (!wanted.contains(baseName)) {
                    continue;
                }
                if (!found.add(baseName)) {
                    throw new IOException("Duplicate archive member: " + baseName);
                }
                File output = new File(destination, baseName);
                try (BufferedOutputStream target = new BufferedOutputStream(
                        new FileOutputStream(output), BUFFER_SIZE)) {
                    int count;
                    while ((count = tarInput.read(buffer)) != -1) {
                        target.write(buffer, 0, count);
                    }
                    target.flush();
                }
            }
        }
        if (!found.equals(wanted)) {
            throw new IOException("Archive is missing requested model files");
        }
    }
}
