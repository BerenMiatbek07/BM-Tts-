"""Dependency-light Microsoft Edge TTS client tuned for Android reliability.

The public functions in this module intentionally match the original app API.
The transport follows the current edge-tts consumer protocol while avoiding
heavy asyncio/aiohttp dependencies that are awkward to package with p4a.
"""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import random
import re
import secrets
import socket as socket_module
import ssl
import time
import urllib.error
import urllib.request
import uuid
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Event, Lock
from typing import Callable

import certifi
import websocket


TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
BASE_URL = "speech.platform.bing.com/consumer/speech/synthesize/readaloud"
WSS_URL = f"wss://{BASE_URL}/edge/v1?TrustedClientToken={TRUSTED_CLIENT_TOKEN}"
VOICE_LIST_URL = (
    f"https://{BASE_URL}/voices/list?trustedclienttoken={TRUSTED_CLIENT_TOKEN}"
)
CHROMIUM_VERSION = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION = CHROMIUM_VERSION.split(".", 1)[0]
SEC_MS_GEC_VERSION = f"1-{CHROMIUM_VERSION}"
WIN_EPOCH = 11_644_473_600
ORIGIN = "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/{CHROMIUM_MAJOR_VERSION}.0.0.0 Safari/537.36 "
    f"Edg/{CHROMIUM_MAJOR_VERSION}.0.0.0"
)

_CLOCK_LOCK = Lock()
_clock_skew_seconds = 0.0


FALLBACK_VOICES = [
    {"ShortName": "kk-KZ-AigulNeural", "Locale": "kk-KZ", "Gender": "Female"},
    {"ShortName": "kk-KZ-DauletNeural", "Locale": "kk-KZ", "Gender": "Male"},
    {"ShortName": "ru-RU-SvetlanaNeural", "Locale": "ru-RU", "Gender": "Female"},
    {"ShortName": "ru-RU-DmitryNeural", "Locale": "ru-RU", "Gender": "Male"},
    {"ShortName": "en-US-AriaNeural", "Locale": "en-US", "Gender": "Female"},
    {"ShortName": "en-US-GuyNeural", "Locale": "en-US", "Gender": "Male"},
    {"ShortName": "en-GB-SoniaNeural", "Locale": "en-GB", "Gender": "Female"},
    {"ShortName": "es-ES-ElviraNeural", "Locale": "es-ES", "Gender": "Female"},
    {"ShortName": "es-ES-AlvaroNeural", "Locale": "es-ES", "Gender": "Male"},
    {"ShortName": "fr-FR-DeniseNeural", "Locale": "fr-FR", "Gender": "Female"},
    {"ShortName": "fr-FR-HenriNeural", "Locale": "fr-FR", "Gender": "Male"},
    {"ShortName": "de-DE-KatjaNeural", "Locale": "de-DE", "Gender": "Female"},
    {"ShortName": "de-DE-ConradNeural", "Locale": "de-DE", "Gender": "Male"},
    {"ShortName": "tr-TR-EmelNeural", "Locale": "tr-TR", "Gender": "Female"},
    {"ShortName": "tr-TR-AhmetNeural", "Locale": "tr-TR", "Gender": "Male"},
    {"ShortName": "it-IT-ElsaNeural", "Locale": "it-IT", "Gender": "Female"},
    {"ShortName": "it-IT-DiegoNeural", "Locale": "it-IT", "Gender": "Male"},
    {"ShortName": "pt-BR-FranciscaNeural", "Locale": "pt-BR", "Gender": "Female"},
    {"ShortName": "pt-BR-AntonioNeural", "Locale": "pt-BR", "Gender": "Male"},
    {"ShortName": "zh-CN-XiaoxiaoNeural", "Locale": "zh-CN", "Gender": "Female"},
    {"ShortName": "zh-CN-YunxiNeural", "Locale": "zh-CN", "Gender": "Male"},
    {"ShortName": "ja-JP-NanamiNeural", "Locale": "ja-JP", "Gender": "Female"},
    {"ShortName": "ja-JP-KeitaNeural", "Locale": "ja-JP", "Gender": "Male"},
    {"ShortName": "ko-KR-SunHiNeural", "Locale": "ko-KR", "Gender": "Female"},
    {"ShortName": "ko-KR-InJoonNeural", "Locale": "ko-KR", "Gender": "Male"},
    {"ShortName": "ar-SA-ZariyahNeural", "Locale": "ar-SA", "Gender": "Female"},
    {"ShortName": "ar-SA-HamedNeural", "Locale": "ar-SA", "Gender": "Male"},
    {"ShortName": "uk-UA-PolinaNeural", "Locale": "uk-UA", "Gender": "Female"},
    {"ShortName": "uk-UA-OstapNeural", "Locale": "uk-UA", "Gender": "Male"},
    {"ShortName": "uz-UZ-MadinaNeural", "Locale": "uz-UZ", "Gender": "Female"},
    {"ShortName": "uz-UZ-SardorNeural", "Locale": "uz-UZ", "Gender": "Male"},
]


class CancelledError(RuntimeError):
    pass


class EdgeTtsError(RuntimeError):
    """Base class for user-facing online TTS failures."""


class EdgeNetworkError(EdgeTtsError):
    pass


class EdgeAuthenticationError(EdgeTtsError):
    pass


class EdgeRateLimitError(EdgeTtsError):
    pass


class EdgeNoAudioError(EdgeTtsError):
    pass


def _get_clock_skew() -> float:
    with _CLOCK_LOCK:
        return _clock_skew_seconds


def _set_clock_skew(value: float) -> None:
    global _clock_skew_seconds
    if abs(value) > 24 * 60 * 60:
        return
    with _CLOCK_LOCK:
        _clock_skew_seconds = float(value)


def _header_value(headers, name: str) -> str | None:
    if not headers:
        return None
    lowered = name.lower()
    try:
        items = headers.items()
    except AttributeError:
        return None
    for key, value in items:
        if str(key).lower() == lowered:
            return str(value)
    return None


def _adjust_clock_from_headers(headers) -> bool:
    server_date = _header_value(headers, "Date")
    if not server_date:
        return False
    try:
        parsed = parsedate_to_datetime(server_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        _set_clock_skew(parsed.timestamp() - time.time())
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def generate_sec_ms_gec(clock_offset_seconds: float = 0.0) -> str:
    ticks = time.time() + _get_clock_skew() + clock_offset_seconds + WIN_EPOCH
    ticks -= ticks % 300
    ticks *= 10_000_000
    payload = f"{ticks:.0f}{TRUSTED_CLIENT_TOKEN}"
    return hashlib.sha256(payload.encode("ascii")).hexdigest().upper()


def _voice_list_request_url() -> str:
    return (
        f"{VOICE_LIST_URL}&Sec-MS-GEC={generate_sec_ms_gec()}"
        f"&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
    )


def _voice_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-CH-UA": (
            f'" Not;A Brand";v="99", "Microsoft Edge";v="{CHROMIUM_MAJOR_VERSION}", '
            f'"Chromium";v="{CHROMIUM_MAJOR_VERSION}"'
        ),
        "Sec-CH-UA-Mobile": "?0",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Cookie": f"muid={secrets.token_hex(16).upper()};",
    }


def list_voices(timeout: int = 20) -> list[dict[str, str]]:
    """Return the online catalogue, falling back to a built-in safe subset."""
    for attempt in range(2):
        request = urllib.request.Request(_voice_list_request_url(), headers=_voice_headers())
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
                context=ssl.create_default_context(cafile=certifi.where()),
            ) as response:
                payload = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    payload = gzip.decompress(payload)
            data = json.loads(payload.decode("utf-8"))
            voices = [
                {"ShortName": str(item.get("ShortName", "")), "Locale": str(item.get("Locale", "")), "Gender": str(item.get("Gender", ""))}
                for item in data if item.get("ShortName") and item.get("Locale")
            ]
            return voices or list(FALLBACK_VOICES)
        except urllib.error.HTTPError as error:
            if error.code == 403 and attempt == 0 and _adjust_clock_from_headers(error.headers):
                continue
            break
        except Exception:
            break
    return list(FALLBACK_VOICES)


def _date_string() -> str:
    return time.strftime(
        "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
        time.gmtime(time.time() + _get_clock_skew()),
    )


def _remove_incompatible_characters(text: str) -> str:
    chars = list(text)
    for index, character in enumerate(chars):
        code = ord(character)
        if (0 <= code <= 8) or (11 <= code <= 12) or (14 <= code <= 31):
            chars[index] = " "
    return "".join(chars)


def _split_utf8(text: str, byte_limit: int = 3800) -> list[str]:
    text = _remove_incompatible_characters(text.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not text:
        return []

    def encoded_length(value: str) -> int:
        return len(html.escape(value, quote=False).encode("utf-8"))

    def split_oversized(value: str) -> list[str]:
        result: list[str] = []
        current = ""
        for token in re.findall(r"\S+\s*", value):
            if encoded_length(token) > byte_limit:
                if current.strip():
                    result.append(current.strip())
                current = ""
                character_part = ""
                for character in token:
                    candidate = character_part + character
                    if character_part and encoded_length(candidate) > byte_limit:
                        result.append(character_part)
                        character_part = character
                    else:
                        character_part = candidate
                if character_part:
                    current = character_part
                continue
            candidate = current + token
            if current and encoded_length(candidate) > byte_limit:
                result.append(current.strip())
                current = token
            else:
                current = candidate
        if current.strip():
            result.append(current.strip())
        return result

    segments = re.findall(r".+?(?:[.!?…]+[\"'»”’)]*(?:\s+|$)|\n+|$)", text, flags=re.DOTALL)
    chunks: list[str] = []
    current = ""
    for segment in segments:
        if encoded_length(segment) > byte_limit:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.extend(split_oversized(segment))
            continue
        candidate = current + segment
        if current and encoded_length(candidate) > byte_limit:
            chunks.append(current.strip())
            current = segment
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def estimate_chunks(text: str) -> int:
    return len(_split_utf8(text))


def _parse_headers(blob: bytes) -> dict[bytes, bytes]:
    headers: dict[bytes, bytes] = {}
    for line in blob.split(b"\r\n"):
        if b":" in line:
            key, value = line.split(b":", 1)
            headers[key.strip()] = value.strip()
    return headers


def _speech_config(output_format: str = "mp3") -> str:
    format_name = "riff-24khz-16bit-mono-pcm" if output_format == "wav" else "audio-24khz-48kbitrate-mono-mp3"
    return (
        f"X-Timestamp:{_date_string()}\r\n"
        "Content-Type:application/json; charset=utf-8\r\n"
        "Path:speech.config\r\n\r\n"
        '{"context":{"synthesis":{"audio":{"metadataoptions":'
        '{"sentenceBoundaryEnabled":"true","wordBoundaryEnabled":"false"},'
        f'"outputFormat":"{format_name}"'
        "}}}}\r\n"
    )


def _ssml_message(text: str, voice: str, rate: int, pitch: int, volume: int, sentence_pause_ms: int = 0) -> str:
    del sentence_pause_ms
    request_id = uuid.uuid4().hex
    escaped = html.escape(_remove_incompatible_characters(text), quote=False)
    rate_value = f"{rate:+d}%"
    pitch_value = f"{pitch:+d}Hz"
    volume_value = f"{volume:+d}%"
    voice_match = re.match(r"^([a-z]{2,})-([A-Z]{2,})-(.+Neural)$", voice)
    if voice_match:
        language, region, name = voice_match.groups()
        if "-" in name:
            region_suffix, name = name.split("-", 1)
            region = f"{region}-{region_suffix}"
        ssml_voice = "Microsoft Server Speech Text to Speech Voice " f"({language}-{region}, {name})"
    else:
        ssml_voice = voice
    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='{html.escape(ssml_voice, quote=True)}'>"
        f"<prosody pitch='{pitch_value}' rate='{rate_value}' volume='{volume_value}'>"
        f"{escaped}</prosody></voice></speak>"
    )
    return (
        f"X-RequestId:{request_id}\r\n"
        "Content-Type:application/ssml+xml\r\n"
        f"X-Timestamp:{_date_string()}Z\r\n"
        "Path:ssml\r\n\r\n"
        f"{ssml}"
    )


def _websocket_url(extra_offset: float = 0.0) -> str:
    return (
        f"{WSS_URL}&ConnectionId={uuid.uuid4().hex}"
        f"&Sec-MS-GEC={generate_sec_ms_gec(extra_offset)}"
        f"&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
    )


def _websocket_headers() -> list[str]:
    return [
        "Pragma: no-cache", "Cache-Control: no-cache", f"User-Agent: {USER_AGENT}",
        "Accept-Encoding: gzip, deflate", "Accept-Language: en-US,en;q=0.9",
    ]


def _connect_websocket():
    last_error: BaseException | None = None
    offsets = [0.0, -300.0, 300.0]
    server_clock_retry_used = False
    for extra_offset in offsets:
        try:
            return websocket.create_connection(
                _websocket_url(extra_offset), timeout=35, header=_websocket_headers(),
                cookie=f"muid={secrets.token_hex(16).upper()};", origin=ORIGIN,
                enable_multithread=True, skip_utf8_validation=True,
                http_no_proxy=["speech.platform.bing.com"],
                sockopt=((socket_module.IPPROTO_TCP, socket_module.TCP_NODELAY, 1), (socket_module.SOL_SOCKET, socket_module.SO_KEEPALIVE, 1)),
                sslopt={"ca_certs": certifi.where(), "cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True},
            )
        except websocket.WebSocketBadStatusException as error:
            last_error = error
            status = int(getattr(error, "status_code", 0) or 0)
            if status == 429:
                raise EdgeRateLimitError("Microsoft TTS temporarily limited requests (HTTP 429).") from error
            if status == 403:
                adjusted = _adjust_clock_from_headers(getattr(error, "resp_headers", None))
                if adjusted and not server_clock_retry_used:
                    server_clock_retry_used = True
                    try:
                        return websocket.create_connection(
                            _websocket_url(), timeout=35, header=_websocket_headers(),
                            cookie=f"muid={secrets.token_hex(16).upper()};", origin=ORIGIN,
                            enable_multithread=True, skip_utf8_validation=True,
                            http_no_proxy=["speech.platform.bing.com"],
                            sockopt=((socket_module.IPPROTO_TCP, socket_module.TCP_NODELAY, 1), (socket_module.SOL_SOCKET, socket_module.SO_KEEPALIVE, 1)),
                            sslopt={"ca_certs": certifi.where(), "cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True},
                        )
                    except Exception as retry_error:
                        last_error = retry_error
                continue
            body = getattr(error, "resp_body", b"")
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
            raise EdgeNetworkError(f"TTS WebSocket handshake failed (HTTP {status}): {str(body)[:160]}") from error
        except websocket.WebSocketTimeoutException as error:
            raise EdgeNetworkError("TTS connection timed out.") from error
        except socket_module.gaierror as error:
            raise EdgeNetworkError("DNS could not resolve the TTS server.") from error
        except ssl.SSLError as error:
            raise EdgeNetworkError("TLS certificate connection failed.") from error
        except (ConnectionError, OSError, websocket.WebSocketException) as error:
            last_error = error
    if isinstance(last_error, websocket.WebSocketBadStatusException):
        status = int(getattr(last_error, "status_code", 0) or 0)
        if status in (401, 403):
            raise EdgeAuthenticationError(f"Microsoft TTS rejected the request (HTTP {status}).") from last_error
    raise EdgeNetworkError(f"Could not connect to Microsoft TTS: {last_error or 'unknown network error'}") from last_error


def _synthesize_piece(text: str, voice: str, rate: int, pitch: int, volume: int, sentence_pause_ms: int = 0, output_format: str = "mp3") -> bytes:
    if not text.strip():
        raise ValueError("Text is empty.")
    output_format = "wav" if output_format == "wav" else "mp3"
    socket = _connect_websocket()
    audio = bytearray()
    try:
        socket.settimeout(65)
        socket.send(_speech_config(output_format), opcode=websocket.ABNF.OPCODE_TEXT)
        socket.send(_ssml_message(text, voice, rate, pitch, volume, sentence_pause_ms=sentence_pause_ms), opcode=websocket.ABNF.OPCODE_TEXT)
        while True:
            try:
                opcode, data = socket.recv_data()
            except websocket.WebSocketTimeoutException as error:
                raise EdgeNetworkError("TTS server response timed out.") from error
            if opcode == websocket.ABNF.OPCODE_BINARY:
                raw = bytes(data)
                if len(raw) < 2:
                    continue
                header_length = int.from_bytes(raw[:2], "big")
                if header_length <= 0 or 2 + header_length > len(raw):
                    continue
                headers_map = _parse_headers(raw[2:2 + header_length])
                payload = raw[2 + header_length:]
                if headers_map.get(b"Path") != b"audio":
                    continue
                content_type = headers_map.get(b"Content-Type")
                if output_format == "mp3" and content_type not in (b"audio/mpeg", None):
                    continue
                if output_format == "wav" and content_type not in (b"audio/wav", b"audio/x-wav", b"audio/riff", b"application/octet-stream", None):
                    continue
                if payload:
                    audio.extend(payload)
            elif opcode == websocket.ABNF.OPCODE_TEXT:
                raw_text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
                header_blob, _, body = raw_text.partition("\r\n\r\n")
                path = _parse_headers(header_blob.encode("utf-8")).get(b"Path")
                if path == b"turn.end":
                    break
                if path == b"response" and "error" in body.lower():
                    raise EdgeTtsError(body[:240])
            elif opcode == websocket.ABNF.OPCODE_CLOSE:
                break
    except (EdgeTtsError, CancelledError):
        raise
    except socket_module.gaierror as error:
        raise EdgeNetworkError("DNS could not resolve the TTS server.") from error
    except ssl.SSLError as error:
        raise EdgeNetworkError("TLS certificate connection failed.") from error
    except (ConnectionError, OSError, websocket.WebSocketException) as error:
        raise EdgeNetworkError(f"TTS connection was interrupted: {error}") from error
    finally:
        try:
            socket.close()
        except Exception:
            pass
    if not audio:
        raise EdgeNoAudioError("The TTS server responded but returned no audio data.")
    if output_format == "wav":
        if not audio.startswith(b"RIFF"):
            raise EdgeNoAudioError("The TTS server returned an invalid WAV stream.")
    elif not (audio.startswith(b"ID3") or audio[:1] == b"\xff"):
        raise EdgeNoAudioError("The TTS server returned an invalid MP3 stream.")
    return bytes(audio)


def _synthesize_piece_wav(text: str, voice: str, rate: int, pitch: int, volume: int, sentence_pause_ms: int = 0) -> bytes:
    return _synthesize_piece(text, voice, rate, pitch, volume, sentence_pause_ms=sentence_pause_ms, output_format="wav")


def _root_cause(error: BaseException) -> BaseException:
    current = error
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        next_error = current.__cause__ or current.__context__
        if next_error is None:
            break
        current = next_error
    return current


def explain_tts_error(error: BaseException, language: str = "kk") -> str:
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    category = "unknown"
    if any(isinstance(item, EdgeRateLimitError) for item in chain): category = "rate"
    elif any(isinstance(item, EdgeAuthenticationError) for item in chain): category = "auth"
    elif any(isinstance(item, EdgeNoAudioError) for item in chain): category = "no_audio"
    elif any(isinstance(item, EdgeNetworkError) for item in chain): category = "network"
    messages = {
        "kk": {"rate": "TTS сервері сұранысты уақытша шектеді. 20–30 секундтан кейін қайта көріңіз.", "auth": "Microsoft TTS сұранысты қабылдамады. Телефонның күн/уақытын «Автоматты» режимге қойып, қайта көріңіз.", "no_audio": "TTS серверіне қосылды, бірақ аудио дерегі келмеді. Басқа онлайн дауысты таңдаңыз немесе қосымша дауысты қолданыңыз.", "network": "Интернет бар болуы мүмкін, бірақ қолданба TTS серверіне қосыла алмады. VPN/Private DNS-ті уақытша өшіріп тексеріңіз.", "unknown": "Аудио жасау кезінде техникалық қате шықты."},
        "ru": {"rate": "Сервер TTS временно ограничил запросы. Повторите через 20–30 секунд.", "auth": "Microsoft TTS отклонил запрос. Включите автоматические дату и время на телефоне и повторите.", "no_audio": "Подключение к TTS есть, но сервер не вернул аудио. Выберите другой онлайн-голос или дополнительный голос.", "network": "Интернет может работать, но приложение не смогло подключиться к серверу TTS. Временно отключите VPN/Private DNS и проверьте снова.", "unknown": "При создании аудио произошла техническая ошибка."},
        "en": {"rate": "The TTS server temporarily limited requests. Try again in 20–30 seconds.", "auth": "Microsoft TTS rejected the request. Enable automatic date and time on the phone, then retry.", "no_audio": "The TTS server connected but returned no audio. Choose another online voice or an additional voice.", "network": "Internet may be working, but the app could not reach the TTS server. Temporarily disable VPN/Private DNS and retry.", "unknown": "A technical error occurred while creating audio."},
    }
    return messages.get(language, messages["en"])[category]


def synthesize_to_mp3(text: str, voice: str, rate: int, pitch: int, volume: int, output_path: Path, progress: Callable[[int, int], None] | None = None, cancel_event: Event | None = None) -> None:
    pieces = _split_utf8(text)
    if not pieces:
        raise ValueError("Мәтін бос.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".part")
    try:
        with temporary.open("wb") as output:
            for index, piece in enumerate(pieces, start=1):
                if cancel_event and cancel_event.is_set():
                    raise CancelledError("Процесс тоқтатылды.")
                last_error: Exception | None = None
                for attempt in range(4):
                    try:
                        output.write(_synthesize_piece(piece, voice, rate, pitch, volume))
                        output.flush()
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt < 3:
                            delay = min(12.0, 1.5 * (2**attempt)) + random.uniform(0.0, 0.8)
                            time.sleep(delay)
                if last_error:
                    raise EdgeTtsError(f"Audio chunk failed: {last_error}") from last_error
                if progress:
                    progress(index, len(pieces))
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
