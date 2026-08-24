"""Small dependency-free XLSX/CSV text importer for desktop and Android."""

from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from kivy.utils import platform

from text_io import coerce_android_uri, decode_text_bytes, get_android_activity


MAX_SPREADSHEET_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_IMPORTED_CHARS = 1_000_000
OLE_COMPOUND_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _append_limited(parts: list[str], value: str, current: int) -> int:
    new_size = current + len(value)
    if new_size > MAX_IMPORTED_CHARS:
        raise ValueError("Spreadsheet text exceeds 1,000,000 characters.")
    parts.append(value)
    return new_size


def _xml_text(element) -> str:
    return "".join(node.text or "" for node in element.iter() if node.tag.rsplit("}", 1)[-1] == "t")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        data = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(data)
    return [_xml_text(item) for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "si"]


def _worksheet_names(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/[^/]+\.xml", name)]
    def natural_key(name: str):
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]
    return sorted(names, key=natural_key)


def _cell_text(cell, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return _xml_text(cell)
    value = next((child.text or "" for child in cell if child.tag.rsplit("}", 1)[-1] == "v"), "")
    if cell_type == "s" and value:
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE"
    return value


def _xlsx_bytes_to_text(data: bytes) -> str:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise ValueError("The selected file is not a valid XLSX workbook.") from error
    with archive:
        total_uncompressed = sum(item.file_size for item in archive.infolist())
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("The XLSX workbook is too large.")
        shared = _shared_strings(archive)
        sheet_names = _worksheet_names(archive)
        if not sheet_names:
            raise ValueError("The XLSX workbook contains no worksheets.")
        output: list[str] = []
        output_size = 0
        wrote_sheet = False
        for sheet_name in sheet_names:
            root = ElementTree.fromstring(archive.read(sheet_name))
            sheet_rows: list[str] = []
            for row in root.iter():
                if row.tag.rsplit("}", 1)[-1] != "row":
                    continue
                values = [_cell_text(cell, shared) for cell in row if cell.tag.rsplit("}", 1)[-1] == "c"]
                sheet_rows.append("\t".join(values))
            while sheet_rows and not sheet_rows[0]: sheet_rows.pop(0)
            while sheet_rows and not sheet_rows[-1]: sheet_rows.pop()
            sheet_text = "\n".join(sheet_rows)
            if not sheet_text: continue
            if wrote_sheet: output_size = _append_limited(output, "\n\n", output_size)
            output_size = _append_limited(output, sheet_text, output_size)
            wrote_sheet = True
        return "".join(output)


def _csv_bytes_to_text(data: bytes) -> str:
    decoded = decode_text_bytes(data)
    if not any(delimiter in decoded for delimiter in (",", ";", "\t", "|")):
        if len(decoded) > MAX_IMPORTED_CHARS:
            raise ValueError("Spreadsheet text exceeds 1,000,000 characters.")
        return decoded
    try:
        dialect = csv.Sniffer().sniff(decoded[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    output: list[str] = []
    output_size = 0
    previous_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_IMPORTED_CHARS)
    try:
        for row_number, row in enumerate(csv.reader(io.StringIO(decoded), dialect)):
            if row_number: output_size = _append_limited(output, "\n", output_size)
            output_size = _append_limited(output, "\t".join(row), output_size)
    finally:
        csv.field_size_limit(previous_limit)
    return "".join(output)


def spreadsheet_bytes_to_text(data: bytes) -> str:
    if len(data) > MAX_SPREADSHEET_BYTES:
        raise ValueError("Spreadsheet file is too large.")
    if data.startswith(OLE_COMPOUND_SIGNATURE):
        raise ValueError("Old .xls files are unsupported. Save the workbook as .xlsx.")
    if zipfile.is_zipfile(io.BytesIO(data)):
        return _xlsx_bytes_to_text(data)
    return _csv_bytes_to_text(data)


def read_spreadsheet_path(path: Path) -> str:
    if path.stat().st_size > MAX_SPREADSHEET_BYTES:
        raise ValueError("Spreadsheet file is too large.")
    return spreadsheet_bytes_to_text(path.read_bytes())


def read_android_spreadsheet_uri(uri) -> str:
    if platform != "android":
        raise RuntimeError("Android URI is available only on Android.")
    uri = coerce_android_uri(uri)
    resolver = get_android_activity().getContentResolver()
    descriptor = resolver.openFileDescriptor(uri, "r")
    if descriptor is None:
        raise OSError("Could not open the selected file.")
    file_descriptor = int(descriptor.detachFd())
    with os.fdopen(file_descriptor, "rb", closefd=True) as source:
        data = source.read(MAX_SPREADSHEET_BYTES + 1)
    return spreadsheet_bytes_to_text(data)
