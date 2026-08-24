from __future__ import annotations

__version__ = "5.6.4-personal"

import locale
import os
import re
import threading
import time
import json
import urllib.request
from pathlib import Path
from typing import Callable

if os.environ.get("ANDROID_PRIVATE"):
    os.environ.setdefault(
        "KIVY_HOME",
        os.path.join(os.environ["ANDROID_PRIVATE"], ".kivy"),
    )
    os.environ.setdefault("KIVY_NO_CONFIG", "1")

from kivy.config import Config
from kivy.utils import platform

if platform != "android":
    Config.set("graphics", "width", os.environ.get("BM_DESKTOP_WIDTH", "1100"))
    Config.set("graphics", "height", os.environ.get("BM_DESKTOP_HEIGHT", "780"))
    Config.set("graphics", "resizable", "1")

try:
    import importlib.util as _bm_importlib_util
    import sys as _bm_sys
    import kivy as _bm_kivy

    _bm_kivy_input_dir = os.path.join(
        os.environ.get("ANDROID_ARGUMENT", ""),
        "_python_bundle",
        "site-packages",
        "kivy",
        "input",
    )
    print("BM_KIVY_SYS_PATH", list(_bm_sys.path))
    print("BM_KIVY_PACKAGE_PATH", list(getattr(_bm_kivy, "__path__", [])))
    print(
        "BM_KIVY_INPUT_FS",
        _bm_kivy_input_dir,
        os.path.exists(_bm_kivy_input_dir),
        os.path.isdir(_bm_kivy_input_dir),
        os.access(_bm_kivy_input_dir, os.R_OK | os.X_OK),
        os.listdir(_bm_kivy_input_dir) if os.path.isdir(_bm_kivy_input_dir) else [],
    )
    _bm_kivy_input_spec = _bm_importlib_util.find_spec("kivy.input")
    print("BM_KIVY_INPUT_SPEC", _bm_kivy_input_spec)
    if _bm_kivy_input_spec is None:
        _bm_kivy_input_init = os.path.join(_bm_kivy_input_dir, "__init__.pyc")
        _bm_kivy_input_spec = _bm_importlib_util.spec_from_file_location(
            "kivy.input",
            _bm_kivy_input_init,
            submodule_search_locations=[_bm_kivy_input_dir],
        )
        print("BM_KIVY_INPUT_MANUAL_SPEC", _bm_kivy_input_spec)
        if _bm_kivy_input_spec is None or _bm_kivy_input_spec.loader is None:
            raise ModuleNotFoundError("Could not create a loader for kivy.input")
        _bm_kivy_input_module = _bm_importlib_util.module_from_spec(
            _bm_kivy_input_spec
        )
        _bm_sys.modules["kivy.input"] = _bm_kivy_input_module
        try:
            _bm_kivy_input_spec.loader.exec_module(_bm_kivy_input_module)
        except BaseException:
            _bm_sys.modules.pop("kivy.input", None)
            raise
    import kivy.input as _bm_kivy_input
    print(
        "BM_KIVY_INPUT_PROBE_OK",
        getattr(_bm_kivy_input, "__file__", ""),
        list(getattr(_bm_kivy_input, "__path__", [])),
    )
except BaseException as _bm_kivy_input_error:
    import traceback as _bm_traceback

    print(
        "BM_KIVY_INPUT_PROBE_ERROR",
        type(_bm_kivy_input_error).__name__,
        repr(_bm_kivy_input_error),
    )
    _bm_traceback.print_exc()

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput

from admob_service import ADMOB_BANNER_UNITS, AdMobBannerManager
from audio_player import MobileAudioPlayer
from audio_transcode import mp3_to_wav
from app_log import (
    configure_logging,
    copy_error_log,
    log_event,
    log_exception,
)
from desktop_io import (
    choose_save_audio_path,
    choose_spreadsheet_file_path,
    choose_text_file_path,
    save_audio_to_path,
)
from edge_service import (
    CancelledError,
    FALLBACK_VOICES,
    _synthesize_piece,
    estimate_chunks,
    explain_tts_error,
    list_voices,
)
from generation import (
    MergeError,
    discard_generation_session,
    generate_one_mp3,
    load_generation_session,
    retry_merge_session,
)
from soniox_generation import (
    estimate_soniox_chunks,
    generate_soniox_mp3,
)
from soniox_service import (
    SONIOX_VOICE_NAMES,
    SonioxTTS,
    soniox_gender,
)
from elevenlabs_generation import (
    estimate_elevenlabs_chunks,
    generate_elevenlabs_mp3,
)
from elevenlabs_service import (
    ELEVENLABS_VOICES,
    ELEVENLABS_VOICE_BY_ID,
    ElevenLabsV3TTS,
)
from offline_voice_catalog import (
    cache_is_fresh,
    compatible_model_id,
    fallback_catalog,
    fetch_official_catalog,
    human_size,
    is_runtime_compatible_model,
    read_cached_catalog,
    write_catalog_cache,
)
from offline_voice_manager import (
    ModelDownloadCancelled,
    VoiceModelManager,
)
from sherpa_generation import (
    estimate_sherpa_chunks,
    generate_one_wav,
    retry_sherpa_merge_session,
    verify_wav_file,
)
from clone_generation import (
    estimate_clone_chunks,
    generate_clone_wav,
    retry_clone_merge_session,
)
from sherpa_probe import sherpa_runtime_diagnostic
from script_logic import (
    FILE_SOURCES,
    FILE_TEXT_LIMIT,
    MANUAL_TTS_LIMIT,
    spoken_character_count,
    text_for_tts,
)
from storage import save_to_public_audio
from spreadsheet_io import read_android_spreadsheet_uri, read_spreadsheet_path
from text_io import (
    android_uri_display_name,
    clipboard_text_details,
    read_android_text_uri,
    read_text_path,
)
from timecode_generation import (
    TimecodeError,
    estimate_timecode_cues,
    generate_timecoded_wav,
    parse_timecode_text,
    retry_timecode_merge_session,
)
from voice_clone_security import (
    CHALLENGE_SECONDS,
    VerificationReason,
    VoiceConsentVerifier,
    cleanup_legacy_verification_data,
    inspect_reference_wave,
    sha256_file,
)
from voice_clone_engine import (
    VoiceCloneModelCancelled,
    VoiceCloneModelError,
    VoiceCloneModelManager,
)
if platform != "android":
    from desktop_omnivoice import (
        DesktopOmniVoiceModelManager,
        get_desktop_omnivoice_engine,
    )
    from desktop_voice_recorder import DesktopVoiceRecorder
from voice_clone_billing import VoiceCloneBilling


MAX_CHARS = FILE_TEXT_LIMIT
MANUAL_MAX_CHARS = MANUAL_TTS_LIMIT
TEXT_PREVIEW_CHARS = 1_000_000
TEXT_FILE_REQUEST = 7314
SPREADSHEET_FILE_REQUEST = 7315
FILE_TEXT_SOURCES = FILE_SOURCES
YOUTUBE_CHANNEL_URL = "https://youtube.com/@mrbmstudio07"
APP_PACKAGE_NAME = "org.bmtts.bmtextspeech"
APP_VERSION_CODE = 102640934
UI_ICON_DIR = Path(__file__).resolve().parent / "assets" / "ui_icons"


def ui_icon(name: str) -> str:
    return str(UI_ICON_DIR / f"{name}.png")


def voice_engine(voice_key: str) -> str:
    value = str(voice_key or "")
    if value.startswith("sherpa:"):
        return "sherpa"
    if value.startswith("clone:"):
        return "clone"
    if value.startswith("soniox:"):
        return "soniox"
    if value.startswith("elevenv3:"):
        return "elevenv3"
    return "edge"
UPDATE_CHECK_URLS = (
    "https://bmtts.org/version.json",
    "https://6a66eee338fa3d24e0a29611--vermillion-tanuki-3ece1a.netlify.app/version.json",
)
# BM Voice Studio violet system, matched to the approved concept artwork.
BLUE = (0.50, 0.20, 1.0, 1)
BLUE_DARK = (0.27, 0.10, 0.78, 1)
GREEN = (0.19, 0.82, 0.35, 1)
RED = (1.0, 0.27, 0.23, 1)
# Stronger contrast for OLED/low-brightness phones.
BG = (0.010, 0.010, 0.050, 1)
CARD = (0.030, 0.030, 0.092, 1)
FIELD = (0.022, 0.022, 0.070, 1)
BORDER = (0.30, 0.18, 0.54, 0.92)
TEXT = (0.98, 0.985, 1.0, 1)
MUTED = (0.74, 0.77, 0.84, 1)

THEMES = {
    "dark": {
        "bg": BG,
        "card": CARD,
        "field": FIELD,
        "border": BORDER,
        "text": TEXT,
        "muted": MUTED,
    },
    "light": {
        "bg": (0.94, 0.955, 0.98, 1),
        "card": (1, 1, 1, 1),
        "field": (0.90, 0.93, 0.97, 1),
        "border": (0.68, 0.73, 0.81, 1),
        "text": (0.035, 0.045, 0.075, 1),
        "muted": (0.28, 0.32, 0.40, 1),
    },
}

Window.clearcolor = BG
Window.softinput_mode = "below_target"
if platform != "android":
    Window.size = (1100, 780)


I18N = {
    "kk": {
        "subtitle": "Мәтіннен табиғи дауысқа",
        "script": "Сценарий",
        "limit": "Мәтін/Қою/TXT/Excel · 1 000 000 таңба",
        "load_txt": "TXT ЖҮКТЕУ",
        "load_excel": "EXCEL ЖҮКТЕУ",
        "paste": "ҚОЮ",
        "clear": "ТАЗАЛАУ",
        "clipboard_empty": "Алмасу буферінде мәтін жоқ.",
        "clipboard_failed": "Clipboard мәтінін оқу мүмкін болмады. Қате журналын көшіріп жіберіңіз.",
        "clipboard_read_ok": "Clipboard толық оқылды: {chars} таңба · {method}",
        "text_imported": "TXT мәтіні жүктелді · {chars} таңба",
        "excel_imported": "Excel мәтіні жүктелді · {chars} таңба",
        "text_pasted": "Мәтін қойылды · {chars} таңба",
        "large_text_loaded": "{chars} таңба толық жүктелді · мәтінді өрістің ішінде сырғытып, өңдеуге болады",
        "manual_long_warning": "Мәтін 1 000 000 таңбадан аспауы керек.",
        "manual_long_status": "Барлығы {total} таңба · толық мәтін дыбысталады",
        "long_file_warning": "Бұл ұзақ мәтін. Бағдарлама оны ішкі бөліктерге бөліп өңдейді, бірақ соңында бір толық MP3 аудио шығарады.",
        "txt_too_large": "TXT файл тым үлкен. Максимум 1 000 000 таңбаға дейін қолдау көрсетіледі.",
        "text_file_error": "Мәтін файлын ашу мүмкін болмады. TXT/UTF-8/UTF-16 файлын таңдаңыз.",
        "spreadsheet_file_error": "Excel/CSV файлын ашу мүмкін болмады. .xlsx немесе .csv таңдаңыз (.xls қолдау жоқ).",
        "choose_text_file": "Мәтін файлын таңдаңыз",
        "choose_spreadsheet_file": "Excel немесе CSV файлын таңдаңыз",
        "open_file": "Ашу",
        "text_editor_hint": "Өңдеу үшін түртіңіз · мәтін ішінде жоғары/төмен сырғытыңыз",
        "text_limit_reached": "1 000 000 таңба лимитіне жетті.",
        "voice_studio": "Дауыс студиясы",
        "speech_language": "Дыбыстау тілі",
        "voice_model": "Дауыс моделі",
        "refresh": "Жаңарту",
        "audio_settings": "Дыбыс баптауы",
        "speed": "Жылдамдық",
        "pitch": "Дауыс биіктігі",
        "volume": "Дыбыс деңгейі",
        "sentence_pause": "Сөйлемдер арасы",
        "pause_none": "Қосымша үзіліс жоқ",
        "pause_short": "Қысқа үзіліс",
        "pause_medium": "Орташа үзіліс",
        "pause_long": "Ұзақ үзіліс",
        "reset_settings": "Әдепкіге қайтару",
        "normal": "Қалыпты",
        "rate_slow": "Баяу",
        "rate_slight_slow": "Сәл баяу",
        "rate_slight_fast": "Сәл жылдам",
        "rate_fast": "Жылдам",
        "rate_very_fast": "Өте жылдам",
        "pitch_low": "Төмен дауыс",
        "pitch_high": "Жоғары дауыс",
        "volume_quiet": "Ақырын",
        "volume_loud": "Қатты",
        "file_settings": "Файл және сақтау",
        "auto": "Автоматты",
        "manual": "Өзім қоямын",
        "filename": "Файл атауы",
        "filename_hint": "Мысалы: менің_аудиом",
        "downloads": "Music/BM Text to Voice ішіне сақталады",
        "ad_title": "ЖАРНАМА",
        "ad_body": "Жарнамалық орын",
        "ad_hint": "Banner 320×50 · AdMob дайын орны",
        "ad_top_body": "Жоғарғы жарнамалық орын",
        "ad_middle_body": "Мәтіннен кейінгі жарнама",
        "ad_bottom_body": "Төменгі жарнамалық орын",
        "ad_top_hint": "Top banner 320×50 · AdMob slot",
        "ad_middle_hint": "Native/banner · мәтін бөлімінен кейін",
        "ad_bottom_hint": "Bottom banner 320×50 · аудио жасау алдында",
        "youtube_prompt_title": "Әзірлеушіні қолдау",
        "youtube_prompt_message": "Қолданба ұнаса, әзірлеушінің YouTube арнасына тіркеліп, видеоларға лайк басып қолдау көрсете аласыз. Бұл міндетті емес — қолданбаны бірден жалғастыра беруге болады.",
        "youtube_open_channel": "АРНАНЫ АШУ",
        "youtube_continue": "ЖАЛҒАСТЫРУ",
        "developer_channel": "Әзірлеуші арнасы",
        "developer_channel_hint": "BM Studio YouTube арнасын ашу",
        "youtube_open_failed": "YouTube арнасын ашу мүмкін болмады. Интернет байланысын тексеріңіз.",
        "generate": "АУДИО ЖАСАУ",
        "cancel": "Тоқтату",
        "ready": "Дайын",
        "review": "Дайын аудионы тыңдап көріңіз",
        "play": "Ойнату",
        "pause": "Кідірту",
        "stop": "Тоқтату",
        "resume": "Жалғастыру",
        "retry_merge": "БІРІКТІРУДІ ҚАЙТАЛАУ",
        "save": "MP3 САҚТАУ",
        "delete": "Жою",
        "loading_voices": "Дауыстар жаңартылып жатыр…",
        "cloud_test": "ДАУЫСТЫ ТЫҢДАУ",
        "cloud_test_ok": "Дауыс тыңдалды.",
        "cloud_test_failed": "Дауысқа қосылмады.",
        "offline_tts_failed": "Бұл дауыс іске қосылмады. Басқа жеңіл дауысты таңдаңыз немесе қолданбаны қайта ашып көріңіз.",
        "technical_error_hidden": "Қате шықты. Қайталап көріңіз. Егер қайталанса, қате журналын көшіріп жіберіңіз.",
        "network_required": "Желіге қосылыңыз. Бұл дауысқа интернет қажет.",
        "voice_ready_hint": "Дауыс дайын.",
        "update_available": "Қолданбаның жаңа нұсқасы шықты. Google Play арқылы жаңартыңыз.",
        "update_now": "ЖАҢАРТУ",
        "later": "Кейін",
        "device_test_failed": "Құрылғыдағы дауыс іске қосылмады.",
        "bridge_missing": "APK ішінде Sherpa bridge класы жоқ. v5.6.2 APK нұсқасын қайта орнатыңыз.",
        "kotlin_missing": "APK ішінде Sherpa-ға қажет Kotlin кітапханасы жоқ немесе ашылмады.",
        "sherpa_jni_missing": "Sherpa JNI/native кітапханалары ашылмады. APK құрылғы архитектурасына немесе 16 KB бет өлшеміне сәйкес емес болуы мүмкін.",
        "fp16_incompatible": "Бұрын таңдалған FP16 дауыс бұл телефонда жұмыс істемейді. Үйлесімді нұсқасы таңдалды — оны бір рет жүктеп алыңыз.",
        "fp16_runtime_error": "Бұл FP16 дауыс Android процессорымен үйлеспейді. FP16 жазуы жоқ дауыс нұсқасын таңдаңыз.",
        "voices_loaded": "{count} дауыс жүктелді",
        "counter": "Барлығы: {chars} · Дыбысталады: {spoken} · Лимит: {limit}",
        "over_limit": "TXT/Excel мәтіні 1 000 000 таңбадан аспауы керек.",
        "manual_over_limit": "Мәтін 1 000 000 таңбадан аспауы керек.",
        "empty_text": "Алдымен сценарий мәтінін енгізіңіз.",
        "generating": "Дыбысталып жатыр · {done}/{total}",
        "audio_ready": "Аудио дайын — тыңдап көріңіз",
        "playing": "Ойнатылып жатыр · {now} / {total}",
        "paused": "Кідіртілді · {now} / {total}",
        "stopped": "Аудио тоқтатылды",
        "saved": "Сақталды: {path}",
        "deleted": "Дайын аудио жойылды",
        "cancelled": "Процесс тоқтатылды",
        "confirm_stop": "Жасалып жатқан аудионы тоқтатқыңыз келе ме?",
        "resume_session": "Аяқталмаған дыбыстау табылды. Жалғастыру керек пе?",
        "generation_failed": "Аудио жасау аяқталмады.",
        "generation_failed_detail": "Аудио жасалмады.\n{detail}",
        "audio_ready_no_preview": "Аудио файлы жасалды, бірақ алдын ала тыңдау ашылмады. Файлды сақтауға болады.",
        "merge_failed": "Аудио бөліктерін біріктіру аяқталмады. Бөліктер сақталды, біріктіруді қайталауға болады.",
        "save_failed": "Аудионы сақтау кезінде қате шықты. Қайталап көріңіз.",
        "playback_failed": "Аудионы алдын ала ойнату мүмкін болмады. Файлды сақтап, басқа ойнатқышта ашуға болады.",
        "copy_error_log": "ҚАТЕ ЖУРНАЛЫН КӨШІРУ",
        "log_copied": "Қате журналы алмасу буферіне көшірілді.",
        "log_empty": "Қате журналы әлі жоқ.",
        "theme_light": "Жарық режим",
        "theme_dark": "Қараңғы режим",
        "theme_to_light": "АҚ",
        "theme_to_dark": "ҚАРА",
        "voice_not_ready": "Бұл дауыс әлі дайын емес немесе интернет қажет.",
        "setting_unsupported": "Бұл дауыс бұл баптауды қолдамайды.",
        "gender_female": "әйел дауысы",
        "gender_male": "ер дауыс",
        "other_language": "Басқа тіл",
        "mode_normal": "Қалыпты",
        "mode_long": "Ұзақ TXT",
        "mode_fast": "Онлайн жылдам",
        "progress_details": "Өңделді: {processed} / {total_chars} таңба\nБөлік: {done} / {total}\nОрындалды: {percent}% · Қалды: {eta}\nБолжам аудио: ≈ {audio_duration}\nРежим: {mode} · Қате бөлік: {failed}\nҚайталау: {retry_status}\nДауыс: {voice}\nБаптау: {settings}\nСоңында 1 толық MP3 жасалады",
        "error": "Қате",
        "confirm_delete": "Сақталмаған аудионы жояйын ба?",
        "confirm_replace": "Алдыңғы сақталмаған аудио жойылып, жаңасы жасалсын ба?",
        "yes": "Иә",
        "no": "Жоқ",
        "close": "Жабу",
        "internet": "Интернет байланысын тексеріңіз.",
        "manual_required": "Файл атауын енгізіңіз.",
        "sample": "Сәлем! Бұл BM Text to Voice мобиль қолданбасы.",
    },
    "ru": {
        "subtitle": "Естественный голос из текста",
        "script": "Сценарий",
        "limit": "Текст/Вставка/TXT/Excel · 1 000 000 символов",
        "load_txt": "ЗАГРУЗИТЬ TXT",
        "load_excel": "ЗАГРУЗИТЬ EXCEL",
        "paste": "ВСТАВИТЬ",
        "clear": "ОЧИСТИТЬ",
        "clipboard_empty": "В буфере обмена нет текста.",
        "clipboard_failed": "Не удалось прочитать текст из буфера. Скопируйте и отправьте журнал ошибок.",
        "clipboard_read_ok": "Буфер прочитан полностью: {chars} символов · {method}",
        "text_imported": "TXT загружен · {chars} символов",
        "excel_imported": "Excel загружен · {chars} символов",
        "text_pasted": "Текст вставлен · {chars} символов",
        "large_text_loaded": "Загружено {chars} символов · текст можно прокручивать и редактировать в поле",
        "manual_long_warning": "Текст не должен превышать 1 000 000 символов.",
        "manual_long_status": "Всего {total} символов · будет озвучен весь текст",
        "long_file_warning": "Это длинный текст. Приложение обработает его внутренними частями, но в конце создаст один полный MP3-файл.",
        "txt_too_large": "TXT файл слишком большой. Поддерживается максимум 1 000 000 символов.",
        "text_file_error": "Не удалось открыть текстовый файл. Выберите TXT/UTF-8/UTF-16.",
        "spreadsheet_file_error": "Не удалось открыть таблицу. Выберите .xlsx или .csv (.xls не поддерживается).",
        "choose_text_file": "Выберите текстовый файл",
        "choose_spreadsheet_file": "Выберите файл Excel или CSV",
        "open_file": "Открыть",
        "text_editor_hint": "Нажмите для редактирования · прокручивайте внутри поля",
        "text_limit_reached": "Достигнут лимит 1 000 000 символов.",
        "voice_studio": "Студия голоса",
        "speech_language": "Язык озвучки",
        "voice_model": "Модель голоса",
        "refresh": "Обновить",
        "audio_settings": "Настройка звука",
        "speed": "Скорость",
        "pitch": "Высота голоса",
        "volume": "Громкость",
        "sentence_pause": "Пауза между предложениями",
        "pause_none": "Без дополнительной паузы",
        "pause_short": "Короткая пауза",
        "pause_medium": "Средняя пауза",
        "pause_long": "Длинная пауза",
        "reset_settings": "Сбросить",
        "normal": "Нормально",
        "rate_slow": "Медленно",
        "rate_slight_slow": "Немного медленнее",
        "rate_slight_fast": "Немного быстрее",
        "rate_fast": "Быстро",
        "rate_very_fast": "Очень быстро",
        "pitch_low": "Низкий голос",
        "pitch_high": "Высокий голос",
        "volume_quiet": "Тихо",
        "volume_loud": "Громко",
        "file_settings": "Файл и сохранение",
        "auto": "Автоматически",
        "manual": "Задать имя",
        "filename": "Имя файла",
        "filename_hint": "Например: мой_голос",
        "downloads": "Сохранится в Music/BM Text to Voice",
        "ad_title": "РЕКЛАМА",
        "ad_body": "Рекламное место",
        "ad_hint": "Banner 320×50 · место для AdMob",
        "ad_top_body": "Верхнее рекламное место",
        "ad_middle_body": "Реклама после текста",
        "ad_bottom_body": "Нижнее рекламное место",
        "ad_top_hint": "Top banner 320×50 · слот AdMob",
        "ad_middle_hint": "Native/banner · после блока текста",
        "ad_bottom_hint": "Bottom banner 320×50 · перед созданием аудио",
        "youtube_prompt_title": "Поддержать разработчика",
        "youtube_prompt_message": "Если вам нравится приложение, вы можете поддержать разработчика: подписаться на YouTube-канал и поставить лайк видео. Это необязательно — приложением можно сразу продолжить пользоваться.",
        "youtube_open_channel": "ОТКРЫТЬ КАНАЛ",
        "youtube_continue": "ПРОДОЛЖИТЬ",
        "developer_channel": "Канал разработчика",
        "developer_channel_hint": "Открыть YouTube-канал BM Studio",
        "youtube_open_failed": "Не удалось открыть YouTube-канал. Проверьте подключение к интернету.",
        "generate": "СОЗДАТЬ АУДИО",
        "cancel": "Остановить",
        "ready": "Готово",
        "review": "Прослушайте готовое аудио",
        "play": "Играть",
        "pause": "Пауза",
        "stop": "Стоп",
        "resume": "Продолжить",
        "retry_merge": "ПОВТОРИТЬ ОБЪЕДИНЕНИЕ",
        "save": "СОХРАНИТЬ MP3",
        "delete": "Удалить",
        "loading_voices": "Обновление голосов…",
        "cloud_test": "СЛУШАТЬ ГОЛОС",
        "cloud_test_ok": "Голос воспроизведён.",
        "cloud_test_failed": "Не удалось подключиться к голосу.",
        "offline_tts_failed": "Этот голос не запустился. Выберите другой лёгкий голос или перезапустите приложение.",
        "technical_error_hidden": "Произошла ошибка. Попробуйте ещё раз. Если повторится, скопируйте журнал ошибок.",
        "network_required": "Подключитесь к интернету. Для этого голоса нужна сеть.",
        "voice_ready_hint": "Голос готов.",
        "update_available": "Вышла новая версия приложения. Обновите через Google Play.",
        "update_now": "ОБНОВИТЬ",
        "later": "Позже",
        "device_test_failed": "Голос на устройстве не запустился.",
        "bridge_missing": "В APK отсутствует класс Sherpa bridge. Переустановите APK версии v5.6.2.",
        "kotlin_missing": "В APK отсутствует или не загружается библиотека Kotlin, необходимая Sherpa.",
        "sherpa_jni_missing": "Не загрузились JNI/native-библиотеки Sherpa. APK может не соответствовать архитектуре устройства или размеру страницы 16 KB.",
        "fp16_incompatible": "Ранее выбранный голос FP16 не работает на этом телефоне. Выбрана совместимая версия — загрузите её один раз.",
        "fp16_runtime_error": "Этот голос FP16 несовместим с процессором Android. Выберите версию голоса без пометки FP16.",
        "voices_loaded": "Загружено голосов: {count}",
        "counter": "Всего: {chars} · Озвучится: {spoken} · Лимит: {limit}",
        "over_limit": "Текст TXT/Excel не должен превышать 1 000 000 символов.",
        "manual_over_limit": "Текст не должен превышать 1 000 000 символов.",
        "empty_text": "Сначала введите текст сценария.",
        "generating": "Создание аудио · {done}/{total}",
        "audio_ready": "Аудио готово — прослушайте его",
        "playing": "Воспроизведение · {now} / {total}",
        "paused": "Пауза · {now} / {total}",
        "stopped": "Аудио остановлено",
        "saved": "Сохранено: {path}",
        "deleted": "Готовое аудио удалено",
        "cancelled": "Процесс остановлен",
        "confirm_stop": "Остановить создаваемое аудио?",
        "resume_session": "Найдена незавершённая генерация. Продолжить?",
        "generation_failed": "Не удалось завершить аудио.",
        "generation_failed_detail": "Аудио не создано.\n{detail}",
        "audio_ready_no_preview": "Аудиофайл создан, но предпрослушивание не открылось. Файл можно сохранить.",
        "merge_failed": "Не удалось объединить аудиочасти. Части сохранены, объединение можно повторить.",
        "save_failed": "Ошибка при сохранении аудио. Попробуйте ещё раз.",
        "playback_failed": "Не удалось открыть предпрослушивание. Сохраните файл и откройте его в другом проигрывателе.",
        "copy_error_log": "КОПИРОВАТЬ ЖУРНАЛ ОШИБОК",
        "log_copied": "Журнал ошибок скопирован в буфер обмена.",
        "log_empty": "Журнал ошибок пока пуст.",
        "theme_light": "Светлая тема",
        "theme_dark": "Тёмная тема",
        "theme_to_light": "СВЕТ",
        "theme_to_dark": "ТЁМН",
        "voice_not_ready": "Этот голос ещё не готов или требуется интернет.",
        "setting_unsupported": "Этот голос не поддерживает эту настройку.",
        "gender_female": "женский голос",
        "gender_male": "мужской голос",
        "other_language": "Другой язык",
        "mode_normal": "Обычный",
        "mode_long": "Длинный TXT",
        "mode_fast": "Онлайн быстро",
        "progress_details": "Обработано: {processed} / {total_chars} символов\nЧасть: {done} / {total}\nГотово: {percent}% · Осталось: {eta}\nОжидаемое аудио: ≈ {audio_duration}\nРежим: {mode} · Ошибок частей: {failed}\nПовтор: {retry_status}\nГолос: {voice}\nНастройки: {settings}\nВ конце будет создан один полный MP3",
        "error": "Ошибка",
        "confirm_delete": "Удалить несохранённое аудио?",
        "confirm_replace": "Удалить предыдущее аудио и создать новое?",
        "yes": "Да",
        "no": "Нет",
        "close": "Закрыть",
        "internet": "Проверьте подключение к интернету.",
        "manual_required": "Введите имя файла.",
        "sample": "Здравствуйте! Это мобильное приложение BM Text to Voice.",
    },
    "en": {
        "subtitle": "Natural voice from your text",
        "script": "Script",
        "limit": "Text/Paste/TXT/Excel · 1,000,000 characters",
        "load_txt": "LOAD TXT",
        "load_excel": "LOAD EXCEL",
        "paste": "PASTE",
        "clear": "CLEAR",
        "clipboard_empty": "The clipboard does not contain text.",
        "clipboard_failed": "Could not read clipboard text. Copy and send the error log.",
        "clipboard_read_ok": "Clipboard read in full: {chars} characters · {method}",
        "text_imported": "TXT loaded · {chars} characters",
        "excel_imported": "Excel loaded · {chars} characters",
        "text_pasted": "Text pasted · {chars} characters",
        "large_text_loaded": "{chars} characters loaded · scroll and edit inside the text box",
        "manual_long_warning": "Text cannot exceed 1,000,000 characters.",
        "manual_long_status": "{total} characters total · the full text will be narrated",
        "long_file_warning": "This is a long text. The app will process it internally in chunks, but the final output will be one complete MP3 file.",
        "txt_too_large": "The TXT file is too large. Maximum supported size is 1,000,000 characters.",
        "text_file_error": "Could not open the text file. Select a TXT/UTF-8/UTF-16 file.",
        "spreadsheet_file_error": "Could not open the spreadsheet. Select .xlsx or .csv (.xls is unsupported).",
        "choose_text_file": "Choose a text file",
        "choose_spreadsheet_file": "Choose an Excel or CSV file",
        "open_file": "Open",
        "text_editor_hint": "Tap to edit · scroll vertically inside the text box",
        "text_limit_reached": "The 1,000,000-character limit was reached.",
        "voice_studio": "Voice studio",
        "speech_language": "Speech language",
        "voice_model": "Voice model",
        "refresh": "Refresh",
        "audio_settings": "Audio settings",
        "speed": "Speed",
        "pitch": "Voice pitch",
        "volume": "Volume",
        "sentence_pause": "Pause between sentences",
        "pause_none": "No extra pause",
        "pause_short": "Short pause",
        "pause_medium": "Medium pause",
        "pause_long": "Long pause",
        "reset_settings": "Reset",
        "normal": "Normal",
        "rate_slow": "Slow",
        "rate_slight_slow": "Slightly slow",
        "rate_slight_fast": "Slightly fast",
        "rate_fast": "Fast",
        "rate_very_fast": "Very fast",
        "pitch_low": "Lower voice",
        "pitch_high": "Higher voice",
        "volume_quiet": "Quiet",
        "volume_loud": "Loud",
        "file_settings": "File and saving",
        "auto": "Automatic",
        "manual": "Custom name",
        "filename": "File name",
        "filename_hint": "Example: my_voice",
        "downloads": "Saved to Music/BM Text to Voice",
        "ad_title": "ADVERTISEMENT",
        "ad_body": "Ad space",
        "ad_hint": "Banner 320×50 · ready for AdMob",
        "ad_top_body": "Top ad space",
        "ad_middle_body": "Ad space after text",
        "ad_bottom_body": "Bottom ad space",
        "ad_top_hint": "Top banner 320×50 · AdMob slot",
        "ad_middle_hint": "Native/banner · after the text section",
        "ad_bottom_hint": "Bottom banner 320×50 · before audio creation",
        "youtube_prompt_title": "Support the developer",
        "youtube_prompt_message": "If you enjoy the app, you can support the developer by subscribing to the YouTube channel and liking a video. This is optional — you can continue using the app right away.",
        "youtube_open_channel": "OPEN CHANNEL",
        "youtube_continue": "CONTINUE",
        "developer_channel": "Developer channel",
        "developer_channel_hint": "Open the BM Studio YouTube channel",
        "youtube_open_failed": "Could not open the YouTube channel. Check your internet connection.",
        "generate": "CREATE AUDIO",
        "cancel": "Cancel",
        "ready": "Ready",
        "review": "Listen to the finished audio",
        "play": "Play",
        "pause": "Pause",
        "stop": "Stop",
        "resume": "Resume",
        "retry_merge": "RETRY MERGE",
        "save": "SAVE MP3",
        "delete": "Delete",
        "loading_voices": "Refreshing voices…",
        "cloud_test": "LISTEN TO VOICE",
        "cloud_test_ok": "Voice played.",
        "cloud_test_failed": "Could not connect to the voice.",
        "offline_tts_failed": "This voice could not start. Choose another lightweight voice or restart the app.",
        "technical_error_hidden": "Something went wrong. Try again. If it repeats, copy the error log.",
        "network_required": "Connect to the internet. This voice needs network access.",
        "voice_ready_hint": "Voice is ready.",
        "update_available": "A new version of the app is available. Update from Google Play.",
        "update_now": "UPDATE",
        "later": "Later",
        "device_test_failed": "The on-device voice could not start.",
        "bridge_missing": "The Sherpa bridge class is missing from the APK. Reinstall the v5.6.2 APK.",
        "kotlin_missing": "The Kotlin runtime required by Sherpa is missing or could not load.",
        "sherpa_jni_missing": "Sherpa JNI/native libraries could not load. The APK may not match the device architecture or 16 KB page size.",
        "fp16_incompatible": "The previously selected FP16 voice cannot run on this phone. A compatible version was selected — download it once.",
        "fp16_runtime_error": "This FP16 voice is incompatible with the Android CPU. Select a voice version without the FP16 label.",
        "voices_loaded": "{count} voices loaded",
        "counter": "Total: {chars} · Narrated: {spoken} · Limit: {limit}",
        "over_limit": "TXT/Excel text cannot exceed 1,000,000 characters.",
        "manual_over_limit": "Text cannot exceed 1,000,000 characters.",
        "empty_text": "Enter your script first.",
        "generating": "Creating audio · {done}/{total}",
        "audio_ready": "Audio is ready — listen before saving",
        "playing": "Playing · {now} / {total}",
        "paused": "Paused · {now} / {total}",
        "stopped": "Audio stopped",
        "saved": "Saved: {path}",
        "deleted": "Draft audio deleted",
        "cancelled": "Generation cancelled",
        "confirm_stop": "Stop the audio currently being generated?",
        "resume_session": "An unfinished generation was found. Resume it?",
        "generation_failed": "Could not finish the audio.",
        "generation_failed_detail": "Audio was not created.\n{detail}",
        "audio_ready_no_preview": "The audio file was created, but preview could not open. You can still save it.",
        "merge_failed": "Could not merge the audio chunks. They were kept so you can retry the merge.",
        "save_failed": "Could not save the audio. Please try again.",
        "playback_failed": "Preview could not open. Save the file and play it in another audio app.",
        "copy_error_log": "COPY ERROR LOG",
        "log_copied": "The error log was copied to the clipboard.",
        "log_empty": "There is no error log yet.",
        "theme_light": "Light mode",
        "theme_dark": "Dark mode",
        "theme_to_light": "LIGHT",
        "theme_to_dark": "DARK",
        "voice_not_ready": "This voice is not ready yet or requires internet.",
        "setting_unsupported": "This voice does not support this setting.",
        "gender_female": "female voice",
        "gender_male": "male voice",
        "other_language": "Other language",
        "mode_normal": "Normal",
        "mode_long": "Long TXT",
        "mode_fast": "Online Fast",
        "progress_details": "Processed: {processed} / {total_chars} characters\nChunk: {done} / {total}\nComplete: {percent}% · Remaining: {eta}\nEstimated audio: ≈ {audio_duration}\nMode: {mode} · Failed chunks: {failed}\nRetry: {retry_status}\nVoice: {voice}\nSettings: {settings}\nThe result will be one complete MP3",
        "error": "Error",
        "confirm_delete": "Delete the unsaved audio?",
        "confirm_replace": "Delete the previous draft and create a new one?",
        "yes": "Yes",
        "no": "No",
        "close": "Close",
        "internet": "Check your internet connection.",
        "manual_required": "Enter a file name.",
        "sample": "Hello! This is the BM Text to Voice mobile app.",
    },
}


I18N["kk"].update(
    {
        "additional_voices": "Қосымша дауыстар",
        "voice_source": "Дауыс көзі",
        "source_all": "Барлығы",
        "source_online": "Негізгі",
        "source_additional": "Қосымша дауыстар",
        "online_label": "",
        "quality_x_low": "Жылдам жеңіл дауыс",
        "quality_low": "Жеңіл дауыс",
        "quality_medium": "Орташа",
        "quality_high": "Жоғары",
        "quality_standard": "Стандарт",
        "voice_status_ready": "Дайын",
        "voice_status_download": "Жүктеу",
        "voice_status_favorite": "Таңдаулы",
        "model_download": "ЖҮКТЕУ",
        "model_resume": "ЖАЛҒАСТЫРУ",
        "model_stop": "ТОҚТАТУ",
        "model_delete": "МОДЕЛЬДІ ЖОЮ",
        "model_ready": "ДАЙЫН",
        "model_favorite": "ТАҢДАУЛЫҒА",
        "model_unfavorite": "ТАҢДАУЛЫДАН АЛУ",
        "model_not_downloaded": "Жүктелмеген · {size}",
        "model_partial": "Жүктеу аяқталмаған · {size}",
        "model_installed": "Дайын · телефонда {size}",
        "model_downloading": "Жүктелуде: {percent}% · {done}/{total} · {speed}/с",
        "model_verifying": "Файл тексеріліп жатыр…",
        "model_extracting": "Дауыс орнатылып жатыр…",
        "model_downloaded": "Дауыс дайын: {name}",
        "model_download_cancelled": "Дауыс жүктеуі тоқтатылды. Кейін жалғастыруға болады.",
        "model_download_failed": "Дауыс толық жүктелмеді. Қайта жалғастырып көріңіз.",
        "model_delete_confirm": "{name} дауысын телефоннан жоясыз ба?",
        "model_deleted": "Дауыс моделі жойылды.",
        "catalog_loaded": "Дауыс тізімі жаңарды · негізгі: {online} · қосымша: {additional} · тіл: {languages}",
        "catalog_fallback": "Қосымша дауыстардың сақталған тізімі ашылды.",
        "preview": "ТАҢДАЛҒАН ДАУЫСТЫ ТЫҢДАУ",
        "preview_ready": "Дауыс тексерілді және ойнатылып жатыр.",
        "download_first": "Алдымен осы дауысты жүктеңіз.",
        "device_mode": "Қосымша дауыс",
        "audio_file_ready": "Нәтиже бір толық аудио файл болады",
        "save": "АУДИО САҚТАУ",
        "downloads": "Music/BM Text to Voice ішіне MP3 немесе WAV сақталады",
    }
)
I18N["ru"].update(
    {
        "additional_voices": "Дополнительные голоса",
        "voice_source": "Источник голоса",
        "source_all": "Все",
        "source_online": "Основные",
        "source_additional": "Дополнительные голоса",
        "online_label": "",
        "quality_x_low": "Быстрый лёгкий голос",
        "quality_low": "Лёгкий голос",
        "quality_medium": "Среднее",
        "quality_high": "Высокое",
        "quality_standard": "Стандарт",
        "voice_status_ready": "Готово",
        "voice_status_download": "Скачать",
        "voice_status_favorite": "Избранное",
        "model_download": "СКАЧАТЬ",
        "model_resume": "ПРОДОЛЖИТЬ",
        "model_stop": "ОСТАНОВИТЬ",
        "model_delete": "УДАЛИТЬ МОДЕЛЬ",
        "model_ready": "ГОТОВО",
        "model_favorite": "В ИЗБРАННОЕ",
        "model_unfavorite": "УБРАТЬ ИЗ ИЗБРАННОГО",
        "model_not_downloaded": "Не загружено · {size}",
        "model_partial": "Загрузка не завершена · {size}",
        "model_installed": "Готово · на телефоне {size}",
        "model_downloading": "Загрузка: {percent}% · {done}/{total} · {speed}/с",
        "model_verifying": "Проверка файла…",
        "model_extracting": "Установка голоса…",
        "model_downloaded": "Голос готов: {name}",
        "model_download_cancelled": "Загрузка остановлена. Её можно продолжить позже.",
        "model_download_failed": "Голос загрузился не полностью. Попробуйте продолжить загрузку.",
        "model_delete_confirm": "Удалить голос {name} с телефона?",
        "model_deleted": "Модель голоса удалена.",
        "catalog_loaded": "Список голосов обновлён · основные: {online} · дополнительные: {additional} · языки: {languages}",
        "catalog_fallback": "Открыт сохранённый каталог дополнительных голосов.",
        "preview": "СЛУШАТЬ ВЫБРАННЫЙ ГОЛОС",
        "preview_ready": "Голос проверен и воспроизводится.",
        "download_first": "Сначала загрузите этот голос.",
        "device_mode": "Дополнительный голос",
        "audio_file_ready": "Результат будет одним полным аудиофайлом",
        "save": "СОХРАНИТЬ АУДИО",
        "downloads": "MP3 или WAV сохраняется в Music/BM Text to Voice",
    }
)
I18N["en"].update(
    {
        "additional_voices": "Additional voices",
        "voice_source": "Voice source",
        "source_all": "All",
        "source_online": "Built-in",
        "source_additional": "Additional voices",
        "online_label": "",
        "quality_x_low": "Fast lightweight voice",
        "quality_low": "Lightweight voice",
        "quality_medium": "Medium",
        "quality_high": "High",
        "quality_standard": "Standard",
        "voice_status_ready": "Ready",
        "voice_status_download": "Download",
        "voice_status_favorite": "Favorite",
        "model_download": "DOWNLOAD",
        "model_resume": "RESUME",
        "model_stop": "STOP",
        "model_delete": "DELETE MODEL",
        "model_ready": "READY",
        "model_favorite": "ADD FAVORITE",
        "model_unfavorite": "REMOVE FAVORITE",
        "model_not_downloaded": "Not downloaded · {size}",
        "model_partial": "Download incomplete · {size}",
        "model_installed": "Ready · {size} on device",
        "model_downloading": "Downloading: {percent}% · {done}/{total} · {speed}/s",
        "model_verifying": "Verifying file…",
        "model_extracting": "Installing voice…",
        "model_downloaded": "Voice ready: {name}",
        "model_download_cancelled": "Download stopped. You can resume it later.",
        "model_download_failed": "The voice was not fully downloaded. Try resuming the download.",
        "model_delete_confirm": "Delete {name} from this device?",
        "model_deleted": "Voice model deleted.",
        "catalog_loaded": "Voice list updated · built-in: {online} · additional: {additional} · languages: {languages}",
        "catalog_fallback": "The saved additional voice catalog was opened.",
        "preview": "LISTEN TO SELECTED VOICE",
        "preview_ready": "Voice test is playing.",
        "download_first": "Download this voice first.",
        "device_mode": "Additional voice",
        "audio_file_ready": "The result will be one complete audio file",
        "save": "SAVE AUDIO",
        "downloads": "MP3 or WAV is saved in Music/BM Text to Voice",
    }
)

I18N["kk"].update(
    {
        "timecode": "ТАЙМКОД",
        "timecode_on": "ТАЙМКОД ҚОСУЛЫ",
        "timecode_off": "ТАЙМКОД ӨШІРУЛІ",
        "timecode_hint": "SRT/VTT немесе [00:00:01 --> 00:00:04] мәтін",
        "timecode_mode": "Таймкод",
        "timecode_loaded": "Таймкод оқылды: {cues} бөлік · {chars} таңба",
        "timecode_invalid": "Таймкод табылмады. SRT/VTT немесе 00:00:01 --> 00:00:04 форматымен енгізіңіз.",
        "timecode_counter": "Таймкод: {cues} бөлік · Мәтін: {chars} · Ұзақтығы: {duration}",
        "timecode_ready": "Таймкод режимі қосылды. Әр жол өз уақытымен дыбысталады.",
    }
)
I18N["ru"].update(
    {
        "timecode": "ТАЙМКОД",
        "timecode_on": "ТАЙМКОД ВКЛ.",
        "timecode_off": "ТАЙМКОД ВЫКЛ.",
        "timecode_hint": "SRT/VTT или [00:00:01 --> 00:00:04] текст",
        "timecode_mode": "Таймкод",
        "timecode_loaded": "Таймкод прочитан: {cues} частей · {chars} символов",
        "timecode_invalid": "Таймкод не найден. Используйте SRT/VTT или формат 00:00:01 --> 00:00:04.",
        "timecode_counter": "Таймкод: {cues} частей · Текст: {chars} · Длительность: {duration}",
        "timecode_ready": "Режим таймкода включён. Каждая реплика будет озвучена по своему времени.",
    }
)
I18N["en"].update(
    {
        "timecode": "TIMECODE",
        "timecode_on": "TIMECODE ON",
        "timecode_off": "TIMECODE OFF",
        "timecode_hint": "SRT/VTT or [00:00:01 --> 00:00:04] text",
        "timecode_mode": "Timecode",
        "timecode_loaded": "Timecode loaded: {cues} cues · {chars} characters",
        "timecode_invalid": "No timecode cues found. Use SRT/VTT or 00:00:01 --> 00:00:04 format.",
        "timecode_counter": "Timecode: {cues} cues · Text: {chars} · Duration: {duration}",
        "timecode_ready": "Timecode mode is on. Each cue will be voiced on its timeline.",
    }
)

# Voice-cloning wizard copy is intentionally kept in one small, complete
# three-language block.  The previous screen exposed four implementation
# sections at once; these labels describe only the action the user needs now.
I18N["kk"].update(
    {
        "clone_wizard_title": "Дауыс клондау",
        "clone_step_sample": "1 · Растау",
        "clone_step_verify": "1 · Растау",
        "clone_step_ready": "2 · Дайын",
        "clone_page1_hint": "Клондау әзірше тек ағылшын мәтініне арналған. Құқықтық растауды қосып, экрандағы қысқа ағылшын мәтінін 5–10 секунд тікелей микрофонға оқыңыз.",
        "clone_page2_hint": "Қосымша тексеру моделі қажет емес.",
        "clone_page3_hint": "Расталған дауыспен мәтінді дыбыстау үшін негізгі модельді бір рет орнатыңыз.",
        "clone_back": "Артқа",
        "clone_next": "Келесі",
        "clone_finish": "Жабу",
        "clone_permission_pending": "Микрофон рұқсатын күтіп тұрмыз…",
        "clone_permission_denied": "Микрофон жабық. Рұқсатты баптаулардан қосыңыз.",
        "clone_permission_ready": "Микрофон дайын",
        "clone_permission_action": "Микрофонға рұқсат беру",
        "clone_open_settings": "Баптауларды ашу",
        "clone_download_paused": "{percent}% сақталды · жалғастыруға болады",
        "clone_stage_download": "{percent}% · жүктелуде",
        "clone_stage_install": "{percent}% · орнатылуда",
        "clone_stage_verify": "{percent}% · файлдар тексерілуде",
        "clone_download_background": "Жүктеу қолданба ашық тұрғанда жалғасады және қайта басталмайды.",
    }
)
I18N["ru"].update(
    {
        "clone_wizard_title": "Клонирование голоса",
        "clone_step_sample": "1 · Подтверждение",
        "clone_step_verify": "1 · Подтверждение",
        "clone_step_ready": "2 · Готово",
        "clone_page1_hint": "Клонирование пока работает только с английским текстом. Примите юридическое подтверждение и прочитайте короткую английскую фразу в микрофон за 5–10 секунд.",
        "clone_page2_hint": "Дополнительная модель проверки не требуется.",
        "clone_page3_hint": "Один раз установите основную модель, чтобы озвучивать текст подтверждённым голосом.",
        "clone_back": "Назад",
        "clone_next": "Далее",
        "clone_finish": "Закрыть",
        "clone_permission_pending": "Ожидаем разрешение на микрофон…",
        "clone_permission_denied": "Микрофон отключён. Разрешите его в настройках.",
        "clone_permission_ready": "Микрофон готов",
        "clone_permission_action": "Разрешить микрофон",
        "clone_open_settings": "Открыть настройки",
        "clone_download_paused": "Сохранено {percent}% · можно продолжить",
        "clone_stage_download": "{percent}% · загрузка",
        "clone_stage_install": "{percent}% · установка",
        "clone_stage_verify": "{percent}% · проверка файлов",
        "clone_download_background": "Загрузка продолжится, пока приложение открыто, и не начнётся заново.",
    }
)
I18N["en"].update(
    {
        "clone_wizard_title": "Voice cloning",
        "clone_step_sample": "1 · Confirm",
        "clone_step_verify": "1 · Confirm",
        "clone_step_ready": "2 · Ready",
        "clone_page1_hint": "Cloning currently supports English text only. Accept the legal attestation and read the short English prompt directly into the microphone for 5–10 seconds.",
        "clone_page2_hint": "No extra verification model is required.",
        "clone_page3_hint": "Install the main model once to create speech with your verified voice.",
        "clone_back": "Back",
        "clone_next": "Next",
        "clone_finish": "Close",
        "clone_permission_pending": "Waiting for microphone permission…",
        "clone_permission_denied": "Microphone is blocked. Allow it in app settings.",
        "clone_permission_ready": "Microphone ready",
        "clone_permission_action": "Allow microphone",
        "clone_open_settings": "Open settings",
        "clone_download_paused": "{percent}% saved · ready to continue",
        "clone_stage_download": "{percent}% · downloading",
        "clone_stage_install": "{percent}% · installing",
        "clone_stage_verify": "{percent}% · checking files",
        "clone_download_background": "The download continues while the app is open and will not restart from zero.",
    }
)

# Copy for the compact BM Voice Studio screen.  Technical ids and engine
# names remain internal; every visible control uses plain user language.
I18N["kk"].update(
    {
        "app_title": "BM Voice Studio",
        "app_tagline": "Мәтінді табиғи дауысқа айналдыр",
        "flow_text": "Мәтін",
        "flow_voice": "Дауыс",
        "flow_audio": "Аудио",
        "text_section": "Мәтін",
        "open_txt_compact": "TXT",
        "open_excel_compact": "Excel",
        "paste_compact": "Қою",
        "clear_compact": "Тазалау",
        "timecode_compact": "Таймкод",
        "voice_select": "Дауыс таңдау",
        "natural_style": "Табиғи стиль",
        "open_voice_library": "Дауыстарды ашу  v",
        "preview_compact": "Үлгіні тыңдау",
        "generate_studio": "АУДИО ЖАСАУ",
        "audio_result": "Аудио нәтижесі",
        "rewind_10": "-10 сек",
        "forward_10": "+10 сек",
        "advanced_settings_compact": "Қосымша баптау",
        "advanced_open": "Ашу  v",
        "advanced_close": "Жабу  ^",
        "save_compact": "Сақтау",
        "delete_compact": "Жою",
        "selected_voice": "Таңдалған дауыс",
    }
)
I18N["ru"].update(
    {
        "app_title": "BM Voice Studio",
        "app_tagline": "Превратите текст в естественную речь",
        "flow_text": "Текст",
        "flow_voice": "Голос",
        "flow_audio": "Аудио",
        "text_section": "Текст",
        "open_txt_compact": "TXT",
        "open_excel_compact": "Excel",
        "paste_compact": "Вставить",
        "clear_compact": "Очистить",
        "timecode_compact": "Таймкод",
        "voice_select": "Выбор голоса",
        "natural_style": "Естественный стиль",
        "open_voice_library": "Открыть голоса  v",
        "preview_compact": "Слушать пример",
        "generate_studio": "СОЗДАТЬ АУДИО",
        "audio_result": "Результат",
        "rewind_10": "-10 сек",
        "forward_10": "+10 сек",
        "advanced_settings_compact": "Дополнительные настройки",
        "advanced_open": "Открыть  v",
        "advanced_close": "Закрыть  ^",
        "save_compact": "Сохранить",
        "delete_compact": "Удалить",
        "selected_voice": "Выбранный голос",
    }
)
I18N["en"].update(
    {
        "app_title": "BM Voice Studio",
        "app_tagline": "Turn text into natural speech",
        "flow_text": "Text",
        "flow_voice": "Voice",
        "flow_audio": "Audio",
        "text_section": "Text",
        "open_txt_compact": "TXT",
        "open_excel_compact": "Excel",
        "paste_compact": "Paste",
        "clear_compact": "Clear",
        "timecode_compact": "Timecode",
        "voice_select": "Choose a voice",
        "natural_style": "Natural style",
        "open_voice_library": "Open voice library  v",
        "preview_compact": "Listen to sample",
        "generate_studio": "CREATE AUDIO",
        "audio_result": "Audio result",
        "rewind_10": "-10 sec",
        "forward_10": "+10 sec",
        "advanced_settings_compact": "Advanced settings",
        "advanced_open": "Open  v",
        "advanced_close": "Close  ^",
        "save_compact": "Save",
        "delete_compact": "Delete",
        "selected_voice": "Selected voice",
    }
)

# Compact studio copy used by the Lumean-inspired mobile flow.  The action
# order stays identical in all three UI languages.
I18N["kk"].update(
    {
        "studio_flow": "1  Мәтін  →  2  Дауыс  →  3  Дайын аудио",
        "picker_search": "Іздеу",
        "voice_preview_hint": "Дауыс үлгісін бірден тыңдап көріңіз",
        "result_name": "Дайын нәтиже",
    }
)
I18N["ru"].update(
    {
        "studio_flow": "1  Текст  →  2  Голос  →  3  Готовое аудио",
        "picker_search": "Поиск",
        "voice_preview_hint": "Сразу прослушайте пример голоса",
        "result_name": "Готовый результат",
    }
)
I18N["en"].update(
    {
        "studio_flow": "1  Text  →  2  Voice  →  3  Ready audio",
        "picker_search": "Search",
        "voice_preview_hint": "Listen to a voice sample instantly",
        "result_name": "Ready result",
    }
)

# Consent + liveness copy. The legal consent is explicit and cloning stays
# locked until both the live speaker and random phrase checks pass.
I18N["kk"].update(
    {
        "voice_clone": "Дауыс клондау",
        "voice_clone_hint": "Өз даусыңызбен клондау · әзірше ағылшын мәтіні",
        "clone_sample_language": "Клон үлгісінің тілі",
        "voice_clone_open": "АШУ",
        "clone_owner_title": "Бұл дауысты қолдануға құқығыңызды растаңыз",
        "clone_owner_info": "Қысқа ағылшын сөздері мен 4 кездейсоқ цифрды 5–10 секунд ішінде тікелей микрофонға оқыңыз.",
        "clone_reference": "Жаңа live дауыс үлгісі",
        "clone_reference_file": "ФАЙЛДАН ЖҮКТЕУ",
        "clone_reference_record": "МИКРОФОНМЕН ЖАЗУ",
        "clone_reference_stop": "ЖАЗУДЫ ТОҚТАТУ",
        "clone_reference_missing": "Live үлгі жоқ · 5–10 секунд микрофон қажет",
        "clone_reference_ready": "Үлгі дайын · {seconds} сек",
        "clone_consent_off": "РАСТАУ ҚАЖЕТ · Мен дауыс иесімін немесе рұқсатым бар",
        "clone_consent_on": "РАСТАЛДЫ · Қауіпсіз клондауға келісемін",
        "clone_legal_notice": "Белгіні қосу арқылы: бұл өз даусыңыз немесе иесінің анық рұқсаты бар екенін; телефонда өңдеуге келісетініңізді; еліктету, алаяқтық, қорқыту не зиян үшін қолданбайтыныңызды растайсыз. Жалған мәлімдеме немесе рұқсатсыз қолдану үшін заң алдындағы жауапкершілікті өзіңіз қабылдайсыз.",
        "clone_challenge": "5–10 секундтық live дауыс үлгісі",
        "clone_start": "МИКРОФОНМЕН ЖАЗУ",
        "clone_cancel": "ЖАЗУДЫ ТОҚТАТУ",
        "clone_read_now": "Төмендегі сөйлемді дауыстап оқыңыз ({seconds} сек):\n{phrase}",
        "clone_verifying": "Live дауыс үлгісі телефонның жабық жадына сақталып жатыр…",
        "clone_verified": "Live үлгі сақталды · құқықтық растау тіркелді",
        "clone_rejected": "Жазба қабылданбады. Мәтінді 5–10 секунд анық оқып, қайта көріңіз.",
        "clone_expired": "10 секунд аяқталды. Жаңа мәтінмен қайта жазыңыз.",
        "clone_microphone_required": "Тексеру жазбасын файлдан таңдауға болмайды. Тек тікелей микрофон қолданылады.",
        "clone_no_playback_notice": "Тек тікелей микрофон: файл жүктеу және алдын ала тыңдау жоқ. Қолданба дауыс иесін автоматты дәлелдемейді; заңдық жауапкершілік сізде.",
        "clone_permission": "Микрофон рұқсатын беріңіз.",
        "clone_reference_error": "Тек тікелей микрофоннан 5–10 секундтық жазба қабылданады.",
        "clone_consent_required": "Алдымен дауыс иесі екеніңізді растап, келісім белгісін қосыңыз.",
        "clone_raw_audio_policy": "Тексеру аяқталған соң уақытша live жазба жойылады. Келісім журналы аудионың өзін сақтамайды.",
        "clone_engine": "2. Нақты дауыс клондау моделі",
        "clone_engine_download": "КЛОНДАУ МОДЕЛІН ЖҮКТЕУ · 156 МБ",
        "clone_engine_ready": "Клондау моделі дайын · телефонда жұмыс істейді",
        "clone_engine_locked": "Алдымен келісімді растап, жаңа live дауыс үлгісін жазыңыз",
        "clone_engine_progress": "Клондау моделі жүктелуде: {percent}%",
        "clone_engine_error": "Клондау моделі толық орнатылмады. Жүктеуді қайта жалғастырыңыз.",
        "clone_profile_ready": "Менің live дауыс үлгім · дайын",
        "clone_language_only": "Android клондау моделі қазір ағылшын мәтінін ғана қолдайды.",
        "clone_private_profile_policy": "Расталған live үлгі мен оның дәл мәтіні тек осы телефонның жабық app storage ішінде сақталады.",
    }
)
I18N["ru"].update(
    {
        "voice_clone": "Клонирование голоса",
        "voice_clone_hint": "Клонирование своим голосом · пока только английский текст",
        "clone_sample_language": "Язык образца для клона",
        "voice_clone_open": "ОТКРЫТЬ",
        "clone_owner_title": "Подтвердите право использовать этот голос",
        "clone_owner_info": "Прочитайте короткие английские слова и 4 случайные цифры напрямую в микрофон за 5–10 секунд.",
        "clone_reference": "Новый live-образец голоса",
        "clone_reference_file": "ЗАГРУЗИТЬ ФАЙЛ",
        "clone_reference_record": "ЗАПИСАТЬ МИКРОФОНОМ",
        "clone_reference_stop": "ОСТАНОВИТЬ ЗАПИСЬ",
        "clone_reference_missing": "Нет live-образца · требуется 5–10 секунд с микрофона",
        "clone_reference_ready": "Образец готов · {seconds} сек",
        "clone_consent_off": "НУЖНО ПОДТВЕРДИТЬ · Я владелец голоса или имею разрешение",
        "clone_consent_on": "ПОДТВЕРЖДЕНО · Согласен на безопасное клонирование",
        "clone_legal_notice": "Включая подтверждение, вы заявляете: это ваш голос либо есть явное разрешение владельца; вы согласны на обработку на телефоне; голос не будет использоваться для имитации личности, мошенничества, угроз или вреда. Вы принимаете юридическую ответственность за ложное заявление или использование без разрешения.",
        "clone_challenge": "Новый live-образец за 5–10 секунд",
        "clone_start": "ЗАПИСАТЬ МИКРОФОНОМ",
        "clone_cancel": "ОСТАНОВИТЬ ЗАПИСЬ",
        "clone_read_now": "Прочитайте вслух фразу ниже ({seconds} сек):\n{phrase}",
        "clone_verifying": "Live-образец сохраняется в закрытом хранилище телефона…",
        "clone_verified": "Live-образец сохранён · юридическое подтверждение записано",
        "clone_rejected": "Запись не принята. Чётко прочитайте текст за 5–10 секунд и повторите.",
        "clone_expired": "10 секунд истекли. Запишите новый текст.",
        "clone_microphone_required": "Файл нельзя использовать для проверки. Требуется прямая запись с микрофона.",
        "clone_no_playback_notice": "Только прямая запись с микрофона: загрузки файла и предварительного прослушивания нет. Приложение не доказывает личность автоматически; юридическая ответственность лежит на вас.",
        "clone_permission": "Разрешите доступ к микрофону.",
        "clone_reference_error": "Принимается только прямая запись с микрофона длительностью 5–10 секунд.",
        "clone_consent_required": "Подтвердите владение голосом и включите согласие.",
        "clone_raw_audio_policy": "После проверки временная live-запись удаляется. В журнале согласия само аудио не хранится.",
        "clone_engine": "2. Настоящая модель клонирования",
        "clone_engine_download": "СКАЧАТЬ МОДЕЛЬ КЛОНИРОВАНИЯ · 156 МБ",
        "clone_engine_ready": "Модель клонирования готова · работает на телефоне",
        "clone_engine_locked": "Сначала примите подтверждение и запишите новый live-образец",
        "clone_engine_progress": "Загрузка модели клонирования: {percent}%",
        "clone_engine_error": "Модель клонирования установлена не полностью. Продолжите загрузку.",
        "clone_profile_ready": "Мой live-образец голоса · готов",
        "clone_language_only": "Android-модель клонирования пока поддерживает только английский текст.",
        "clone_private_profile_policy": "Подтверждённый live-образец и его точный текст хранятся только в закрытом хранилище приложения на этом телефоне.",
    }
)
I18N["en"].update(
    {
        "voice_clone": "Voice cloning",
        "voice_clone_hint": "Clone your own voice · English text only for now",
        "clone_sample_language": "Clone sample language",
        "voice_clone_open": "OPEN",
        "clone_owner_title": "Confirm your right to use this voice",
        "clone_owner_info": "Read short English words and 4 random digits directly into the microphone for 5–10 seconds.",
        "clone_reference": "Fresh live voice sample",
        "clone_reference_file": "UPLOAD FILE",
        "clone_reference_record": "RECORD WITH MICROPHONE",
        "clone_reference_stop": "STOP RECORDING",
        "clone_reference_missing": "No live sample · 5–10 microphone seconds required",
        "clone_reference_ready": "Sample ready · {seconds} sec",
        "clone_consent_off": "CONFIRM REQUIRED · I own this voice or have permission",
        "clone_consent_on": "CONFIRMED · I consent to safe voice cloning",
        "clone_legal_notice": "By confirming, you state that this is your voice or you have the owner's explicit permission; you consent to on-device processing; and you will not use the voice for impersonation, fraud, threats, harassment, or harm. You accept legal responsibility for a false statement or unauthorized use.",
        "clone_challenge": "Fresh 5–10 second live sample",
        "clone_start": "RECORD WITH MICROPHONE",
        "clone_cancel": "STOP RECORDING",
        "clone_read_now": "Read the phrase below aloud ({seconds} sec):\n{phrase}",
        "clone_verifying": "Saving the live sample in this phone's private storage…",
        "clone_verified": "Live sample saved · legal attestation recorded",
        "clone_rejected": "The recording was not accepted. Read clearly for 5–10 seconds and try again.",
        "clone_expired": "The 10-second window expired. Record a fresh prompt.",
        "clone_microphone_required": "A file cannot be used for the live check. Record directly from the microphone.",
        "clone_no_playback_notice": "Direct microphone only: no file upload or pre-verification playback. The app does not automatically prove identity; legal responsibility remains with you.",
        "clone_permission": "Allow microphone access.",
        "clone_reference_error": "Only a direct 5–10 second microphone recording is accepted.",
        "clone_consent_required": "Confirm ownership and enable consent first.",
        "clone_raw_audio_policy": "The temporary live recording is deleted after verification. The consent receipt does not store raw audio.",
        "clone_engine": "2. Real voice-cloning model",
        "clone_engine_download": "DOWNLOAD CLONING MODEL · 156 MB",
        "clone_engine_ready": "Cloning model ready · runs on this phone",
        "clone_engine_locked": "Accept the attestation and record a fresh live sample first",
        "clone_engine_progress": "Downloading cloning model: {percent}%",
        "clone_engine_error": "The cloning model is incomplete. Resume the download.",
        "clone_profile_ready": "My live voice sample · ready",
        "clone_language_only": "The Android cloning model currently supports English text only.",
        "clone_private_profile_policy": "The verified live sample and its exact transcript stay only in this phone's private app storage.",
    }
)


LANGUAGE_NAMES = {
    "kk": {"kk": "Қазақ тілі", "ru": "Казахский язык", "en": "Kazakh"},
    "ru": {"kk": "Орыс тілі", "ru": "Русский язык", "en": "Russian"},
    "en": {"kk": "Ағылшын тілі", "ru": "Английский язык", "en": "English"},
    "tr": {"kk": "Түрік тілі", "ru": "Турецкий язык", "en": "Turkish"},
    "es": {"kk": "Испан тілі", "ru": "Испанский язык", "en": "Spanish"},
    "de": {"kk": "Неміс тілі", "ru": "Немецкий язык", "en": "German"},
    "fr": {"kk": "Француз тілі", "ru": "Французский язык", "en": "French"},
    "it": {"kk": "Итальян тілі", "ru": "Итальянский язык", "en": "Italian"},
    "pt": {"kk": "Португал тілі", "ru": "Португальский язык", "en": "Portuguese"},
    "zh": {"kk": "Қытай тілі", "ru": "Китайский язык", "en": "Chinese"},
    "ja": {"kk": "Жапон тілі", "ru": "Японский язык", "en": "Japanese"},
    "ko": {"kk": "Корей тілі", "ru": "Корейский язык", "en": "Korean"},
    "ar": {"kk": "Араб тілі", "ru": "Арабский язык", "en": "Arabic"},
    "uk": {"kk": "Украин тілі", "ru": "Украинский язык", "en": "Ukrainian"},
    "uz": {"kk": "Өзбек тілі", "ru": "Узбекский язык", "en": "Uzbek"},
}

# Every language currently returned by the cloud voice catalogue has a real
# user-facing name. Locale/voice IDs remain internal and never become labels.
LANGUAGE_NAMES.update(
    {
        "no": {"kk": "Норвег тілі", "ru": "Норвежский язык", "en": "Norwegian"},
        "lb": {"kk": "Люксембург тілі", "ru": "Люксембургский язык", "en": "Luxembourgish"},
        "ku": {"kk": "Күрд тілі", "ru": "Курдский язык", "en": "Kurdish"},
        "af": {"kk": "Африкаанс", "ru": "Африкаанс", "en": "Afrikaans"},
        "am": {"kk": "Амхар тілі", "ru": "Амхарский язык", "en": "Amharic"},
        "az": {
            "kk": "Әзербайжан тілі",
            "ru": "Азербайджанский язык",
            "en": "Azerbaijani",
        },
        "bg": {"kk": "Болгар тілі", "ru": "Болгарский язык", "en": "Bulgarian"},
        "bn": {"kk": "Бенгал тілі", "ru": "Бенгальский язык", "en": "Bengali"},
        "bs": {"kk": "Босния тілі", "ru": "Боснийский язык", "en": "Bosnian"},
        "ca": {"kk": "Каталан тілі", "ru": "Каталанский язык", "en": "Catalan"},
        "cs": {"kk": "Чех тілі", "ru": "Чешский язык", "en": "Czech"},
        "cy": {"kk": "Уэльс тілі", "ru": "Валлийский язык", "en": "Welsh"},
        "da": {"kk": "Дат тілі", "ru": "Датский язык", "en": "Danish"},
        "el": {"kk": "Грек тілі", "ru": "Греческий язык", "en": "Greek"},
        "et": {"kk": "Эстон тілі", "ru": "Эстонский язык", "en": "Estonian"},
        "fa": {"kk": "Парсы тілі", "ru": "Персидский язык", "en": "Persian"},
        "fi": {"kk": "Фин тілі", "ru": "Финский язык", "en": "Finnish"},
        "fil": {
            "kk": "Филиппин тілі",
            "ru": "Филиппинский язык",
            "en": "Filipino",
        },
        "ga": {"kk": "Ирланд тілі", "ru": "Ирландский язык", "en": "Irish"},
        "gl": {"kk": "Галисия тілі", "ru": "Галисийский язык", "en": "Galician"},
        "gu": {"kk": "Гуджарати", "ru": "Гуджарати", "en": "Gujarati"},
        "he": {"kk": "Иврит", "ru": "Иврит", "en": "Hebrew"},
        "hi": {"kk": "Хинди", "ru": "Хинди", "en": "Hindi"},
        "hr": {"kk": "Хорват тілі", "ru": "Хорватский язык", "en": "Croatian"},
        "hu": {"kk": "Мажар тілі", "ru": "Венгерский язык", "en": "Hungarian"},
        "id": {
            "kk": "Индонезия тілі",
            "ru": "Индонезийский язык",
            "en": "Indonesian",
        },
        "is": {"kk": "Исланд тілі", "ru": "Исландский язык", "en": "Icelandic"},
        "iu": {"kk": "Инуктитут", "ru": "Инуктитут", "en": "Inuktitut"},
        "jv": {"kk": "Ява тілі", "ru": "Яванский язык", "en": "Javanese"},
        "ka": {"kk": "Грузин тілі", "ru": "Грузинский язык", "en": "Georgian"},
        "km": {"kk": "Кхмер тілі", "ru": "Кхмерский язык", "en": "Khmer"},
        "kn": {"kk": "Каннада", "ru": "Каннада", "en": "Kannada"},
        "lo": {"kk": "Лаос тілі", "ru": "Лаосский язык", "en": "Lao"},
        "lt": {"kk": "Литва тілі", "ru": "Литовский язык", "en": "Lithuanian"},
        "lv": {"kk": "Латыш тілі", "ru": "Латышский язык", "en": "Latvian"},
        "mk": {
            "kk": "Македон тілі",
            "ru": "Македонский язык",
            "en": "Macedonian",
        },
        "ml": {"kk": "Малаялам", "ru": "Малаялам", "en": "Malayalam"},
        "mn": {"kk": "Моңғол тілі", "ru": "Монгольский язык", "en": "Mongolian"},
        "mr": {"kk": "Маратхи", "ru": "Маратхи", "en": "Marathi"},
        "ms": {"kk": "Малай тілі", "ru": "Малайский язык", "en": "Malay"},
        "mt": {"kk": "Мальта тілі", "ru": "Мальтийский язык", "en": "Maltese"},
        "my": {"kk": "Бирма тілі", "ru": "Бирманский язык", "en": "Burmese"},
        "nb": {"kk": "Норвег тілі", "ru": "Норвежский язык", "en": "Norwegian"},
        "ne": {"kk": "Непал тілі", "ru": "Непальский язык", "en": "Nepali"},
        "nl": {
            "kk": "Нидерланд тілі",
            "ru": "Нидерландский язык",
            "en": "Dutch",
        },
        "pl": {"kk": "Поляк тілі", "ru": "Польский язык", "en": "Polish"},
        "ps": {"kk": "Пушту", "ru": "Пушту", "en": "Pashto"},
        "ro": {"kk": "Румын тілі", "ru": "Румынский язык", "en": "Romanian"},
        "si": {"kk": "Сингал тілі", "ru": "Сингальский язык", "en": "Sinhala"},
        "sk": {"kk": "Словак тілі", "ru": "Словацкий язык", "en": "Slovak"},
        "sl": {"kk": "Словен тілі", "ru": "Словенский язык", "en": "Slovenian"},
        "so": {"kk": "Сомали тілі", "ru": "Сомалийский язык", "en": "Somali"},
        "sq": {"kk": "Албан тілі", "ru": "Албанский язык", "en": "Albanian"},
        "sr": {"kk": "Серб тілі", "ru": "Сербский язык", "en": "Serbian"},
        "su": {"kk": "Сундан тілі", "ru": "Сунданский язык", "en": "Sundanese"},
        "sv": {"kk": "Швед тілі", "ru": "Шведский язык", "en": "Swedish"},
        "sw": {"kk": "Суахили", "ru": "Суахили", "en": "Swahili"},
        "ta": {"kk": "Тамил тілі", "ru": "Тамильский язык", "en": "Tamil"},
        "te": {"kk": "Телугу", "ru": "Телугу", "en": "Telugu"},
        "th": {"kk": "Тай тілі", "ru": "Тайский язык", "en": "Thai"},
        "ur": {"kk": "Урду", "ru": "Урду", "en": "Urdu"},
        "vi": {
            "kk": "Вьетнам тілі",
            "ru": "Вьетнамский язык",
            "en": "Vietnamese",
        },
        "zu": {"kk": "Зулу", "ru": "Зулу", "en": "Zulu"},
    }
)

OFFLINE_VOICE_NAMES = {
    "iseke": {"kk": "Исеке", "ru": "Исеке", "en": "Iseke"},
    "raya": {"kk": "Рая", "ru": "Рая", "en": "Raya"},
    "issai": {"kk": "ISSAI", "ru": "ISSAI", "en": "ISSAI"},
}


VOICE_NAMES = {
    "Aigul": {"kk": "Айгүл", "ru": "Айгуль", "en": "Aigul"},
    "Daulet": {"kk": "Дәулет", "ru": "Даулет", "en": "Daulet"},
    "Svetlana": {"kk": "Светлана", "ru": "Светлана", "en": "Svetlana"},
    "Dmitry": {"kk": "Дмитрий", "ru": "Дмитрий", "en": "Dmitry"},
    "Aria": {"kk": "Aria", "ru": "Aria", "en": "Aria"},
    "Jenny": {"kk": "Jenny", "ru": "Jenny", "en": "Jenny"},
    "Guy": {"kk": "Guy", "ru": "Guy", "en": "Guy"},
    "Sonia": {"kk": "Sonia", "ru": "Sonia", "en": "Sonia"},
}


class StableSlider(Slider):
    """Use a numeric default that also works in packaged Windows builds."""

    value_track_width = NumericProperty(3)


class Card(BoxLayout):
    bg_color = ListProperty(CARD)
    border_color = ListProperty(BORDER)
    radius = NumericProperty(dp(22))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg = Color(*self.bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        with self.canvas.after:
            self._border_color = Color(*self.border_color)
            self._border = Line(
                rounded_rectangle=(*self.pos, *self.size, self.radius),
                width=1.15,
            )
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            bg_color=self._update_canvas,
            border_color=self._update_canvas,
            radius=self._update_canvas,
        )

    def _update_canvas(self, *_):
        self._bg.rgba = self.bg_color
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self.radius]
        self._border_color.rgba = self.border_color
        self._border.rounded_rectangle = (*self.pos, *self.size, self.radius)

    def on_touch_down(self, touch):
        # A zero-height BoxLayout still dispatches touches to its fixed-height
        # children. Collapsed progress/review cards must therefore opt out
        # explicitly or their invisible disabled controls cover the actions
        # shown above them in the ScrollView.
        if self.height <= 0 or self.opacity <= 0:
            return False
        return super().on_touch_down(touch)


class StyledButton(Button):
    fill_color = ListProperty(BLUE)
    border_color = ListProperty(BLUE)
    radius = NumericProperty(dp(14))

    def __init__(self, **kwargs):
        self.theme_role = kwargs.pop("role", "")
        requested_fill = kwargs.get("fill_color", BLUE)
        if not self.theme_role:
            if requested_fill == FIELD:
                self.theme_role = "secondary"
            elif requested_fill == GREEN:
                self.theme_role = "success"
            elif requested_fill == RED:
                self.theme_role = "danger"
            else:
                self.theme_role = "primary"
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", TEXT)
        kwargs.setdefault("disabled_color", (0.55, 0.57, 0.62, 1))
        kwargs.setdefault("font_size", "14sp")
        super().__init__(**kwargs)
        with self.canvas.before:
            self._fill = Color(*self.fill_color)
            self._shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        with self.canvas.after:
            self._line_color = Color(*self.border_color)
            self._line = Line(
                rounded_rectangle=(*self.pos, *self.size, self.radius),
                width=1.25,
            )
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            fill_color=self._update_canvas,
            border_color=self._update_canvas,
            radius=self._update_canvas,
            disabled=self._update_canvas,
        )

    def _update_canvas(self, *_):
        fill = self.fill_color
        self._fill.rgba = (*fill[:3], fill[3] * (0.45 if self.disabled else 1))
        self._shape.pos = self.pos
        self._shape.size = self.size
        self._shape.radius = [self.radius]
        self._line_color.rgba = self.border_color
        self._line.rounded_rectangle = (*self.pos, *self.size, self.radius)


class IconActionButton(StyledButton):
    """A normal accessible button with a bundled PNG icon overlay."""

    icon_source = StringProperty("")
    icon_size = NumericProperty(dp(30))
    icon_centered = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._icon_core = None
        self._icon_available = False
        with self.canvas.after:
            self._icon_tint = Color(1, 1, 1, 1)
            self._icon_rect = Rectangle(pos=self.pos, size=(0, 0))
        self.bind(
            pos=self._update_png_icon,
            size=self._update_png_icon,
            icon_source=self._load_png_icon,
            icon_size=self._update_png_icon,
            icon_centered=self._update_png_icon,
            disabled=self._update_png_icon,
        )
        self._load_png_icon()

    def _load_png_icon(self, *_args) -> None:
        try:
            if self.icon_source and Path(self.icon_source).is_file():
                self._icon_core = CoreImage(self.icon_source)
                self._icon_rect.texture = self._icon_core.texture
                self._icon_available = True
            else:
                self._icon_core = None
                self._icon_available = False
                self._icon_rect.texture = None
        except Exception as error:
            self._icon_core = None
            self._icon_available = False
            self._icon_rect.texture = None
            log_exception("ui_icon_load", error)
        self._update_png_icon()

    def _update_png_icon(self, *_args) -> None:
        if not self._icon_available:
            self._icon_rect.size = (0, 0)
            return
        side = min(float(self.icon_size), max(0.0, self.height - dp(8)))
        if self.icon_centered or not self.text:
            x = self.center_x - side / 2
        else:
            x = self.x + dp(8)
        self._icon_rect.pos = (x, self.center_y - side / 2)
        self._icon_rect.size = (side, side)
        self._icon_tint.rgba = (1, 1, 1, 0.42 if self.disabled else 1)


class WaveBadge(Label):
    """Font-independent voice mark drawn directly on the Kivy canvas."""

    bg_color = ListProperty((0.20, 0.07, 0.46, 1))
    border_color = ListProperty((0.58, 0.25, 1.0, 0.9))
    icon_color = ListProperty((0.82, 0.63, 1.0, 1))
    radius = NumericProperty(dp(14))

    def __init__(self, **kwargs):
        kwargs.setdefault("text", "")
        super().__init__(**kwargs)
        with self.canvas.before:
            self._badge_fill_color = Color(*self.bg_color)
            self._badge_fill = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self.radius]
            )
        with self.canvas.after:
            self._badge_border_color = Color(*self.border_color)
            self._badge_border = Line(
                rounded_rectangle=(*self.pos, *self.size, self.radius), width=1.2
            )
            self._badge_icon_color = Color(*self.icon_color)
            self._badge_bars = [Line(points=[0, 0, 0, 0], width=2.0) for _ in range(5)]
        self.bind(
            pos=self._update_badge,
            size=self._update_badge,
            bg_color=self._update_badge,
            border_color=self._update_badge,
            icon_color=self._update_badge,
            radius=self._update_badge,
        )
        self._update_badge()

    def _update_badge(self, *_args) -> None:
        self._badge_fill_color.rgba = self.bg_color
        self._badge_fill.pos = self.pos
        self._badge_fill.size = self.size
        self._badge_fill.radius = [self.radius]
        self._badge_border_color.rgba = self.border_color
        self._badge_border.rounded_rectangle = (*self.pos, *self.size, self.radius)
        self._badge_icon_color.rgba = self.icon_color
        center_x = self.x + self.width / 2
        center_y = self.y + self.height / 2
        spacing = max(dp(4), self.width * 0.075)
        heights = (0.28, 0.58, 0.82, 0.58, 0.28)
        for index, (bar, scale) in enumerate(zip(self._badge_bars, heights)):
            x = center_x + (index - 2) * spacing
            half = self.height * scale * 0.28
            bar.points = [x, center_y - half, x, center_y + half]


class CanvasIconButton(StyledButton):
    """Button whose play/pause mark never depends on an Android font."""

    icon_kind = StringProperty("play")
    icon_color = ListProperty((1, 1, 1, 1))

    def __init__(self, **kwargs):
        kwargs.setdefault("text", "")
        super().__init__(**kwargs)
        with self.canvas.after:
            self._icon_canvas_color = Color(*self.icon_color)
            self._icon_line_a = Line(points=[0, 0, 0, 0], width=2.4)
            self._icon_line_b = Line(points=[0, 0, 0, 0], width=2.4)
        self.bind(
            pos=self._update_icon,
            size=self._update_icon,
            icon_kind=self._update_icon,
            icon_color=self._update_icon,
            disabled=self._update_icon,
        )
        self._update_icon()

    def _update_icon(self, *_args) -> None:
        alpha = 0.45 if self.disabled else 1.0
        color = self.icon_color
        self._icon_canvas_color.rgba = (*color[:3], color[3] * alpha)
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        unit = max(dp(6), min(self.width, self.height) * 0.18)
        if self.icon_kind == "pause":
            self._icon_line_a.points = [cx - unit * 0.55, cy - unit, cx - unit * 0.55, cy + unit]
            self._icon_line_b.points = [cx + unit * 0.55, cy - unit, cx + unit * 0.55, cy + unit]
        else:
            self._icon_line_a.points = [
                cx - unit * 0.65,
                cy - unit,
                cx + unit,
                cy,
                cx - unit * 0.65,
                cy + unit,
                cx - unit * 0.65,
                cy - unit,
            ]
            self._icon_line_b.points = []


class PrimaryActionButton(StyledButton):
    """Large studio action with a restrained violet glow."""

    def __init__(self, **kwargs):
        kwargs.setdefault("fill_color", BLUE)
        kwargs.setdefault("border_color", (0.72, 0.36, 1.0, 1))
        kwargs.setdefault("role", "primary")
        kwargs.setdefault("radius", dp(17))
        super().__init__(**kwargs)
        with self.canvas.before:
            self._glow_color = Color(0.46, 0.16, 1.0, 0.24)
            self._glow = Line(
                rounded_rectangle=(*self.pos, *self.size, self.radius),
                width=dp(5),
            )
        self.bind(pos=self._update_glow, size=self._update_glow, disabled=self._update_glow)

    def _update_glow(self, *_args) -> None:
        self._glow_color.rgba = (0.46, 0.16, 1.0, 0.08 if self.disabled else 0.24)
        self._glow.rounded_rectangle = (*self.pos, *self.size, self.radius)


class BMSpinnerOption(SpinnerOption):
    """Compact dropdown row that keeps long voice names readable."""

    def __init__(self, **kwargs):
        app = App.get_running_app()
        palette = THEMES.get(getattr(app, "theme", "dark"), THEMES["dark"])
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", palette["field"])
        kwargs.setdefault("color", palette["text"])
        kwargs.setdefault("font_size", "13sp")
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("shorten", True)
        kwargs.setdefault("shorten_from", "right")
        super().__init__(**kwargs)
        self.bind(size=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *_args) -> None:
        self.text_size = (max(0, self.width - dp(24)), None)


class BMSpinnerDropDown(DropDown):
    """Bounded dropdown so a long voice catalog stays inside the screen."""

    def __init__(self, **kwargs):
        kwargs.setdefault(
            "max_height",
            min(dp(420), max(dp(230), float(Window.height) * 0.56)),
        )
        super().__init__(**kwargs)


class BMSpinner(Spinner):
    """Theme-aware, bounded spinner used by all mobile selectors."""

    def __init__(self, **kwargs):
        kwargs.setdefault("dropdown_cls", BMSpinnerDropDown)
        kwargs.setdefault("option_cls", BMSpinnerOption)
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("shorten", True)
        kwargs.setdefault("shorten_from", "right")
        super().__init__(**kwargs)
        self.bind(size=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *_args) -> None:
        self.text_size = (max(0, self.width - dp(24)), None)


class ModernPickerButton(StyledButton):
    """Searchable, phone-sized selector that replaces the old long dropdown."""

    values = ListProperty([])
    picker_title = StringProperty("")
    picker_app = ObjectProperty(None, allownone=True)
    preview_callback = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("fill_color", FIELD)
        kwargs.setdefault("border_color", BORDER)
        kwargs.setdefault("role", "secondary")
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("padding", (dp(16), 0))
        super().__init__(**kwargs)
        self.bind(size=self._align_text)
        self.bind(on_release=lambda *_: self.open_picker())

    def _align_text(self, *_args) -> None:
        self.text_size = (max(0, self.width - dp(36)), None)
        self.valign = "middle"

    def open_picker(self) -> None:
        if self.disabled or not self.values:
            return
        app = self.picker_app
        if app:
            app._set_picker_menu_open(True)

        sheet = Card(
            orientation="vertical",
            padding=(dp(14), dp(12)),
            spacing=dp(8),
            bg_color=CARD,
            border_color=BORDER,
            radius=dp(26),
        )
        title = make_label(
            self.picker_title or "Select", height=32, font_size="17sp", bold=True
        )
        search = styled_input(height=44)
        search.hint_text = app.t("picker_search") if app else "Search"
        option_scroll = ScrollView(
            do_scroll_x=False, bar_width=dp(3), bar_color=BLUE,
            always_overscroll=False,
        )
        option_list = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(7)
        )
        option_list.bind(minimum_height=option_list.setter("height"))
        option_scroll.add_widget(option_list)
        close_button = StyledButton(
            text=app.t("close") if app else "Close", size_hint_y=None, height=dp(44),
            fill_color=FIELD, border_color=BORDER, role="secondary",
        )
        sheet.add_widget(title)
        sheet.add_widget(search)
        sheet.add_widget(option_scroll)
        sheet.add_widget(close_button)
        popup = Popup(
            title="",
            content=sheet,
            size_hint=(0.94, None),
            height=min(dp(620), Window.height * 0.78),
            separator_height=0,
            background_color=(0, 0, 0, 0),
            auto_dismiss=True,
        )

        def choose(choice: str) -> None:
            self.text = choice
            popup.dismiss()

        def render_options(*_args) -> None:
            option_list.clear_widgets()
            needle = (search.text or "").casefold().strip()
            options = [item for item in self.values if needle in item.casefold()]
            if not options:
                option_list.add_widget(
                    make_label("No results", height=48, color=MUTED)
                )
                return
            for option in options:
                selected = option == self.text
                button = StyledButton(
                    text=option,
                    size_hint_y=None,
                    height=dp(52),
                    padding=(dp(14), 0),
                    halign="left",
                    font_size="14sp",
                    fill_color=BLUE if selected else FIELD,
                    border_color=BLUE if selected else BORDER,
                    role="primary" if selected else "secondary",
                )
                button.bind(
                    size=lambda item, *_: setattr(
                        item, "text_size", (item.width - dp(28), None)
                    )
                )
                button.bind(
                    on_release=lambda _button, choice=option: choose(choice)
                )
                if self.preview_callback is None:
                    option_list.add_widget(button)
                    continue

                # Voice rows have an independent preview action.  Listening must
                # never change the selected voice or close this picker.
                row = BoxLayout(
                    size_hint_y=None,
                    height=dp(56),
                    spacing=dp(7),
                )
                button.height = dp(56)
                preview = IconActionButton(
                    text="",
                    size_hint=(None, None),
                    size=(dp(56), dp(56)),
                    icon_source=ui_icon("play"),
                    icon_size=dp(36),
                    icon_centered=1,
                    fill_color=FIELD,
                    border_color=BLUE,
                    role="secondary",
                )
                preview.bind(
                    on_release=lambda _button, choice=option: self.preview_callback(choice)
                )
                row.add_widget(button)
                row.add_widget(preview)
                option_list.add_widget(row)

        def closed(*_args) -> None:
            if app:
                app._set_picker_menu_open(False)

        search.bind(text=render_options)
        close_button.bind(on_release=lambda *_: popup.dismiss())
        popup.bind(on_dismiss=closed)
        render_options()
        popup.open()


class ScriptTextInput(TextInput):
    """Phone-friendly editor with its own vertical scrolling."""

    max_chars = NumericProperty(1_000_000)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.outer_scroll = None
        self._editor_touch = None
        self._editor_start_y = 0.0
        self._editor_start_scroll_y = 0.0
        self._editor_dragging = False
        self._outer_restore_event = None
        self.limit_callback = None

    def insert_text(self, substring, from_undo=False):
        selection_length = len(self.selection_text or "")
        available = int(self.max_chars) - (len(self.text) - selection_length)
        if available <= 0:
            if callable(self.limit_callback):
                self.limit_callback()
            return
        if len(substring) > available:
            substring = substring[:available]
            if callable(self.limit_callback):
                self.limit_callback()
        log_event(
            "text_insert",
            inserted_text_length=len(substring),
            text_input_length=len(self.text),
            source="manual",
        )
        return super().insert_text(substring, from_undo=from_undo)

    def _max_internal_scroll(self) -> float:
        try:
            line_count = max(1, len(self._lines))
            line_height = float(self.line_height or dp(18))
            return max(0.0, line_count * line_height - self.height + dp(32))
        except Exception:
            return max(0.0, float(self.scroll_y) + self.height * 2)

    def _restore_outer_scroll(self, _dt=0) -> None:
        self._outer_restore_event = None
        if self.outer_scroll is not None:
            self.outer_scroll.do_scroll_y = True

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self.disabled:
            return super().on_touch_down(touch)
        self.focus = True
        self._editor_touch = touch.uid
        self._editor_start_y = touch.y
        self._editor_start_scroll_y = float(self.scroll_y)
        self._editor_dragging = False
        if self.outer_scroll is not None:
            self.outer_scroll.do_scroll_y = False
        if self._outer_restore_event is not None:
            try:
                self._outer_restore_event.cancel()
            except Exception:
                pass
        # Safety reset prevents the whole page from remaining locked if
        # Android cancels a touch while the keyboard opens.
        self._outer_restore_event = Clock.schedule_once(
            self._restore_outer_scroll,
            6.0,
        )
        touch.ud["bm_script_editor"] = True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.ud.get("bm_script_editor") and self._editor_touch == touch.uid:
            delta = self._editor_start_y - touch.y
            if abs(delta) >= dp(7):
                self._editor_dragging = True
                self.scroll_y = min(
                    self._max_internal_scroll(),
                    max(0.0, self._editor_start_scroll_y + delta),
                )
                return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        owned = touch.ud.get("bm_script_editor") and self._editor_touch == touch.uid
        if owned:
            dragging = self._editor_dragging
            self._editor_touch = None
            self._editor_dragging = False
            if self._outer_restore_event is not None:
                try:
                    self._outer_restore_event.cancel()
                except Exception:
                    pass
                self._outer_restore_event = None
            Clock.schedule_once(self._restore_outer_scroll, 0.03)
            if dragging:
                return True
        return super().on_touch_up(touch)

    def on_focus(self, _instance, focused):
        if not focused:
            self._restore_outer_scroll(0)


def make_label(
    text: str = "",
    height: float = 28,
    font_size: str = "14sp",
    color=TEXT,
    bold: bool = False,
    halign: str = "left",
) -> Label:
    label = Label(
        text=f"[b]{text}[/b]" if bold else text,
        markup=True,
        size_hint_y=None,
        height=dp(height),
        color=color,
        font_size=font_size,
        halign=halign,
        valign="middle",
    )
    label.theme_role = (
        "muted"
        if color == MUTED
        else "success"
        if color == GREEN
        else "danger"
        if color == RED
        else "text"
    )
    label.bind(size=lambda widget, _value: setattr(widget, "text_size", (widget.width, None)))
    return label


def styled_input(
    multiline: bool = False,
    height: float = 50,
    script: bool = False,
) -> TextInput:
    input_class = ScriptTextInput if script else TextInput
    return input_class(
        multiline=multiline,
        size_hint_y=None,
        height=dp(height),
        background_normal="",
        background_active="",
        background_color=FIELD,
        foreground_color=TEXT,
        hint_text_color=MUTED,
        cursor_color=BLUE,
        padding=(dp(14), dp(13)),
        font_size="15sp",
        write_tab=False,
        keyboard_suggestions=True,
        cursor_blink=True,
    )


def styled_spinner() -> ModernPickerButton:
    return ModernPickerButton(
        size_hint_y=None,
        height=dp(50),
        background_normal="",
        color=TEXT,
        font_size="14sp",
    )


class BMVoiceMobileApp(App):
    title = "BM Text to Voice"

    def build(self):
        configure_logging(self.user_data_dir)
        self.store = JsonStore(str(Path(self.user_data_dir) / "settings.json"))
        saved = self.store.get("app") if self.store.exists("app") else {}
        self.ui_language = saved.get("ui_language", self._system_language())
        self.theme = saved.get("theme", "dark")
        self.voices = list(FALLBACK_VOICES)
        self.voices_by_language: dict[str, list[dict[str, str]]] = {}
        self.language_display_to_code: dict[str, str] = {}
        self.model_display_to_voice: dict[str, str] = {}
        self.voice_manager = VoiceModelManager(self.user_data_dir)
        self.voice_clone_models = (
            VoiceCloneModelManager(self.user_data_dir)
            if platform == "android"
            else DesktopOmniVoiceModelManager(self.user_data_dir)
        )
        self.desktop_voice_recorder = (
            None if platform == "android" else DesktopVoiceRecorder()
        )
        self.soniox_tts = SonioxTTS(Path(self.user_data_dir) / "soniox_cookies.json")
        self.elevenlabs_api_key = str(saved.get("elevenlabs_api_key", "") or "").strip()
        self.clone_reference_language = (
            "en"
            if platform == "android"
            else str(saved.get("clone_reference_language", "kk")).split("-", 1)[0].lower()
        )
        if self.clone_reference_language not in {"kk", "ru", "en"}:
            self.clone_reference_language = "kk" if platform != "android" else "en"
        self._cleanup_legacy_voice_verification_async()
        self.clone_billing = VoiceCloneBilling(
            self.user_data_dir,
            personal_unlimited=platform != "android",
        )
        self.clone_billing_poll = None
        self.clone_billing_event_version = -1
        self.clone_quota_count_pending = False
        self.voice_consent = VoiceConsentVerifier()
        self.voice_reference_seconds = 0.0
        self.voice_consent_popup: Popup | None = None
        self.voice_consent_record_purpose = ""
        self.voice_consent_record_started_at = 0.0
        self.voice_consent_record_poll = None
        self.pending_microphone_action = ""
        self.microphone_permission_poll = None
        self.voice_clone_model_worker: threading.Thread | None = None
        self.voice_clone_model_cancel = threading.Event()
        self.voice_consent_challenge_id = ""
        self.voice_consent_capture_started_at = 0.0
        self.voice_consent_live_path = ""
        self.voice_consent_cancel_requested = False
        self.offline_catalog = (
            read_cached_catalog(self.voice_manager.catalog_cache) or fallback_catalog()
        )
        self.offline_catalog = self._merge_installed_voice_catalog(self.offline_catalog)
        self.offline_model_by_id = {
            str(item["id"]): item for item in self.offline_catalog
        }
        self.voice_source = saved.get("voice_source", "all")
        if self.voice_source not in ("all", "edge", "sherpa"):
            self.voice_source = "all"
        self.favorite_voices = set(saved.get("favorite_voices", []))
        self.download_worker: threading.Thread | None = None
        self.download_cancel_event = threading.Event()
        self.active_download_model_id = ""
        self.preferred_language = saved.get("speech_language", "kk")
        self.preferred_voice = saved.get("voice_id", "")
        self._voice_precision_migrated = False
        if self.preferred_voice and not self.preferred_voice.startswith(("edge:", "sherpa:", "clone:", "soniox:", "elevenv3:")):
            self.preferred_voice = f"edge:{self.preferred_voice}"
        if self.preferred_voice.startswith("sherpa:"):
            saved_model_id = self.preferred_voice.split(":", 1)[1]
            compatible_id = compatible_model_id(saved_model_id)
            if compatible_id != saved_model_id:
                self.preferred_voice = f"sherpa:{compatible_id}"
                self._voice_precision_migrated = True
        self.naming_mode = saved.get("naming_mode", "auto")
        self.youtube_prompt_shown = bool(saved.get("youtube_prompt_shown", False))
        self.full_script_text = ""
        self.script_source = "manual"
        self.timecode_mode = bool(saved.get("timecode_mode", False))
        self.is_manual_over_limit = False
        self.source_file_name = ""
        self._setting_script_text = False
        self._text_status_state: tuple[str, dict[str, str]] | None = None
        self._activity_result_bound = False
        self._android_result_poll_event = None
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self.generation_started_at = 0.0
        self.generation_mode = "mode_normal"
        self.session_dir = Path(self.user_data_dir) / "generation_session"
        self.draft_path: Path | None = None
        self.player = MobileAudioPlayer()
        self.play_started = False
        self._voice_preview_busy = False
        self._polling_review_slider = False
        self.ad_slot_labels: dict[str, tuple[Label, Label, Label]] = {}
        self.ad_slot_widgets: dict[str, Card] = {}
        self.admob_manager = AdMobBannerManager()
        self._app_open_ad_requested = False
        self._active_popup: Popup | None = None
        self._open_spinners: set[Spinner] = set()
        self.advanced_settings_open = bool(saved.get("advanced_settings_open", False))
        self.flow_stage = 1
        self._ui_busy = False

        log_event(
            "persistent_voice_storage",
            root=str(self.voice_manager.root),
            installed=sorted(self.voice_manager.installed_model_ids()),
            clone_model=self.voice_clone_models.is_installed(),
            clone_profile=self.voice_clone_models.has_profile(),
        )

        root = BoxLayout(orientation="vertical")
        self.root_layout = root
        root.add_widget(self._build_top_bar())

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(4),
            bar_color=BLUE,
            bar_inactive_color=(0.35, 0.42, 0.55, 0.55),
            scroll_distance=dp(16),
            scroll_timeout=250,
            always_overscroll=False,
        )
        self.scroll = scroll
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(10), dp(10), dp(10), dp(22)),
            spacing=dp(10),
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        scroll.add_widget(self.content)
        root.add_widget(scroll)

        self._build_intro()
        self._build_text_card()
        self._build_voice_card()
        self._build_voice_clone_card()
        self._build_actions()
        self._build_advanced_toggle()
        self._build_audio_card()
        self._build_file_card()
        self._build_developer_card()
        # Native banners remain in a dedicated safe area below the complete
        # Text -> Voice -> Audio flow.  They never split the editor, selector,
        # primary action, or player.
        self._build_ad_card("top")
        self._build_ad_card("middle")
        self._build_ad_card("bottom")
        self.apply_ui_language(self.ui_language)
        self._apply_voices(self.voices)
        self._restore_settings(saved)
        self.apply_theme(self.theme)
        self._set_advanced_settings(self.advanced_settings_open, save=False)
        self._update_flow_steps()
        self._update_primary_action_state()

        Clock.schedule_interval(self._poll_player, 0.25)
        if platform == "android":
            self._android_result_poll_event = Clock.schedule_interval(
                self._poll_android_activity_result,
                0.15,
            )
        Clock.schedule_once(self._start_admob_banners, 5.0)
        return root

    @staticmethod
    def _system_language() -> str:
        try:
            if platform == "android":
                from jnius import autoclass

                Locale = autoclass("java.util.Locale")
                code = str(Locale.getDefault().getLanguage())
            else:
                code = (locale.getlocale()[0] or "en").split("_", 1)[0]
        except Exception:
            code = "en"
        return code if code in I18N else "en"

    def _save_location_hint(self) -> str:
        if platform == "android":
            return self.t("downloads")
        if self.ui_language == "kk":
            return "Windows: MP3 немесе WAV файлын Save As арқылы сақтайсыз"
        if self.ui_language == "ru":
            return "Windows: MP3 или WAV сохраняется через обычное окно Save As"
        return "Windows: choose where to save MP3 or WAV with Save As"

    def _save_settings(self, **updates) -> None:
        saved = self.store.get("app") if self.store.exists("app") else {}
        saved.update(updates)
        self.store.put("app", **saved)

    def _restore_settings(self, saved: dict) -> None:
        self.rate_slider.value = int(saved.get("rate", 0))
        self.pitch_slider.value = int(saved.get("pitch", 0))
        self.volume_slider.value = int(saved.get("volume", 0))
        self.pause_setting_ms = 0
        self.set_naming_mode(self.naming_mode)
        self._refresh_pause_spinner()

    def _build_top_bar(self) -> BoxLayout:
        compact = Window.width <= dp(340)
        bar = Card(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(80 if compact else 102),
            padding=(dp(8 if compact else 14), dp(10 if compact else 14)),
            spacing=dp(6 if compact else 10),
            radius=0,
            bg_color=BG,
            border_color=(0.12, 0.08, 0.24, 1),
        )
        logo = Image(
            source=ui_icon("waveform"),
            fit_mode="contain",
            size_hint=(None, None),
            size=(dp(34 if compact else 48), dp(34 if compact else 48)),
        )
        logo.theme_role = "fixed_light"
        bar.add_widget(logo)

        title_stack = BoxLayout(orientation="vertical", spacing=0)
        self.title_label = make_label(
            "BM Voice Studio",
            height=32 if compact else 42,
            font_size="14sp" if compact else "18sp",
            bold=True,
        )
        self.subtitle_label = make_label(
            "",
            height=0 if compact else 26,
            font_size="1sp" if compact else "9sp",
            color=MUTED,
        )
        self.subtitle_label.opacity = 0 if compact else 1
        title_stack.add_widget(self.title_label)
        title_stack.add_widget(self.subtitle_label)
        bar.add_widget(title_stack)

        controls = BoxLayout(
            size_hint=(None, None),
            size=(dp(90 if compact else 118), dp(38 if compact else 44)),
            spacing=dp(4 if compact else 6),
        )
        self.ui_language_buttons = {}
        self.ui_language_picker = ModernPickerButton(
            text="KZ  v",
            values=["Қазақша", "Русский", "English"],
            picker_title="Interface language",
            size_hint=(None, None),
            size=(dp(50 if compact else 68), dp(38 if compact else 44)),
            padding=(dp(5 if compact else 10), 0),
            font_size="10sp" if compact else "12sp",
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
        )
        self.ui_language_picker.picker_app = self
        self.ui_language_picker.bind(text=self._on_ui_language_picker)
        controls.add_widget(self.ui_language_picker)

        self.theme_button = IconActionButton(
            text="",
            icon_source=ui_icon("theme"),
            icon_centered=1,
            icon_size=dp(28 if compact else 36),
            size_hint=(None, None),
            size=(dp(36 if compact else 44), dp(38 if compact else 44)),
            fill_color=FIELD,
            border_color=BLUE,
            color=BLUE,
            role="secondary",
        )
        self.theme_button.bind(on_release=lambda *_: self.toggle_theme())
        controls.add_widget(self.theme_button)
        bar.add_widget(controls)
        return bar

    def _new_card(self, height: float) -> Card:
        card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(height),
            padding=(dp(14), dp(12)),
            spacing=dp(6),
        )
        self.content.add_widget(card)
        return card

    def _build_intro(self) -> None:
        card = self._new_card(56)
        card.padding = (dp(10), dp(5))
        card.bg_color = BG
        card.border_color = (0, 0, 0, 0)
        self.ready_label = make_label("", height=0, color=MUTED)
        self.ready_label.opacity = 0
        self.flow_label = make_label("", height=0, color=MUTED)
        self.flow_label.opacity = 0
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.flow_step_buttons = []
        for index in range(3):
            step = StyledButton(
                text=str(index + 1),
                size_hint_y=None,
                height=dp(38),
                fill_color=FIELD,
                border_color=BORDER,
                role="secondary",
                font_size="12sp",
            )
            self.flow_step_buttons.append(step)
            row.add_widget(step)
            if index < 2:
                arrow = make_label(">", height=38, color=MUTED, halign="center")
                arrow.size_hint_x = None
                arrow.width = dp(18)
                row.add_widget(arrow)
        card.add_widget(row)

    def _build_ad_card(self, slot: str) -> None:
        card = self._new_card(60)
        card.padding = (dp(4), dp(4))
        card.spacing = 0
        title_label = make_label("", height=0, font_size="1sp", halign="center")
        body_label = make_label("", height=0, font_size="1sp", halign="center")
        hint_label = make_label("", height=0, font_size="1sp", halign="center")
        title_label.opacity = 0
        body_label.opacity = 0
        hint_label.opacity = 0
        card.add_widget(title_label)
        card.add_widget(body_label)
        card.add_widget(hint_label)
        self.ad_slot_labels[slot] = (title_label, body_label, hint_label)
        self.ad_slot_widgets[slot] = card

    def _on_spinner_open_state(self, spinner: Spinner, is_open: bool) -> None:
        if is_open:
            self._open_spinners.add(spinner)
        else:
            self._open_spinners.discard(spinner)
        # Native AdMob views sit above Kivy's canvas. Hide them immediately
        # while a selector is open so they cannot cut through the dropdown.
        Clock.schedule_once(self._sync_admob_banners, 0)

    def _set_picker_menu_open(self, opened: bool) -> None:
        marker = "modern_picker"
        if opened:
            self._open_spinners.add(marker)
        else:
            self._open_spinners.discard(marker)
        Clock.schedule_once(self._sync_admob_banners, 0)

    def _bind_spinner_menu(self, picker: ModernPickerButton) -> None:
        picker.picker_app = self

    def _start_admob_banners(self, _dt=0) -> None:
        if platform != "android":
            return
        self.admob_manager.start()
        for index, slot in enumerate(ADMOB_BANNER_UNITS):
            Clock.schedule_once(
                lambda _dt, selected=slot: self.admob_manager.load_banner(selected),
                0.8 * index,
            )
        self.admob_manager.preload_interstitial()
        # Preload first, then request App Open only after the Kivy UI has
        # settled. Java limits it to one attempt per process and a short
        # display window, so it cannot appear unexpectedly much later.
        pass  # App Open is handled by BmLaunchActivity before SDL starts
        pass  # App Open is handled by BmLaunchActivity before SDL starts
        self.scroll.bind(scroll_y=lambda *_: self._sync_admob_banners(0))
        Window.bind(on_resize=lambda *_: self._sync_admob_banners(0))
        Clock.schedule_once(self._sync_admob_banners, 0.8)
        Clock.schedule_interval(self._sync_admob_banners, 0.9)

    def _show_delayed_app_open(self, _dt=0) -> None:
        if platform != "android" or self._app_open_ad_requested:
            return
        self._app_open_ad_requested = True
        try:
            pass  # App Open is handled by BmLaunchActivity before SDL starts
        except Exception as error:
            log_exception("admob_app_open_delayed_show_failed", error)

    def _sync_admob_banners(self, _dt=0) -> None:
        if platform != "android":
            return
        for slot, widget in self.ad_slot_widgets.items():
            try:
                x, y = widget.to_window(widget.x, widget.y)
                _scroll_x, scroll_y = self.scroll.to_window(
                    self.scroll.x, self.scroll.y
                )
            except Exception as error:
                log_exception(f"admob_widget_position_failed_{slot}", error)
                continue
            height = float(widget.height)
            viewport_bottom = max(0.0, float(scroll_y))
            viewport_top = min(
                float(Window.height),
                float(scroll_y + self.scroll.height),
            )
            # Native Android views are not clipped by Kivy's ScrollView.
            # Require the complete placeholder to be visible so a partially
            # off-screen ad cannot intercept the audio/create controls.
            edge = float(dp(2))
            visible = (
                y >= viewport_bottom + edge
                and y + height <= viewport_top - edge
                and not self._open_spinners
                and self._active_popup is None
            )
            self.admob_manager.update_banner_frame(
                slot=slot,
                x=float(x),
                y=float(y),
                width=float(widget.width),
                height=height,
                window_height=float(Window.height),
                visible=visible,
            )

    def _build_text_card(self) -> None:
        compact = Window.width <= dp(340)
        card = self._new_card(200)
        card.padding = (dp(12), dp(10))
        card.spacing = dp(5)
        card.border_color = (0.38, 0.20, 0.70, 1)
        header = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(5))
        header_icon = Image(
            source=ui_icon("document"),
            fit_mode="contain",
            size_hint=(None, None),
            size=(dp(22), dp(22)),
        )
        header_icon.theme_role = "fixed_light"
        self.script_label = make_label("", height=24, font_size="14sp", bold=True)
        self.script_label.size_hint_x = 0.42
        self.limit_label = make_label(
            "", height=24, color=MUTED, halign="right", font_size="9sp"
        )
        self.limit_label.size_hint_x = 0.52
        header.add_widget(header_icon)
        header.add_widget(self.script_label)
        header.add_widget(self.limit_label)
        card.add_widget(header)
        tools = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(5))
        self.load_text_button = IconActionButton(
            font_size="7sp" if compact else "8sp",
            icon_source="" if compact else ui_icon("document"), icon_size=dp(20)
        )
        self.load_excel_button = IconActionButton(
            font_size="7sp" if compact else "8sp",
            icon_source="" if compact else ui_icon("spreadsheet"), icon_size=dp(20)
        )
        self.paste_button = IconActionButton(
            font_size="7sp" if compact else "8sp",
            icon_source="" if compact else ui_icon("clipboard"), icon_size=dp(20),
            fill_color=FIELD, border_color=BORDER, role="secondary"
        )
        self.timecode_button = IconActionButton(
            size_hint_y=None,
            height=dp(34),
            font_size="11sp",
            icon_source=ui_icon("timecode"),
            icon_size=dp(27),
            fill_color=FIELD,
            border_color=BORDER,
        )
        self.clear_text_button = IconActionButton(
            font_size="7sp" if compact else "8sp",
            icon_source="" if compact else ui_icon("trash"),
            icon_size=dp(20),
            fill_color=FIELD,
            border_color=BORDER,
        )
        self.load_text_button.bind(on_release=lambda *_: self.open_text_file())
        self.load_excel_button.bind(
            on_release=lambda *_: self.open_spreadsheet_file()
        )
        self.paste_button.bind(on_release=lambda *_: self.paste_large_text())
        self.timecode_button.bind(on_release=lambda *_: self.toggle_timecode_mode())
        self.clear_text_button.bind(on_release=lambda *_: self.clear_script())
        for tool_button in (
            self.load_text_button,
            self.load_excel_button,
            self.paste_button,
            self.clear_text_button,
        ):
            tool_button.halign = "center" if compact else "right"
            tool_button.bind(
                size=lambda item, *_: setattr(
                    item, "text_size", (max(dp(24), item.width - dp(12)), None)
                )
            )
            tools.add_widget(tool_button)
        card.add_widget(tools)
        # Timecode remains available under "Advanced settings" so the main
        # editor keeps the exact compact four-action layout from the mock-up.
        self.text_editor_hint_label = make_label(
            "", height=0, color=MUTED, font_size="9sp", halign="left"
        )
        self.text_editor_hint_label.opacity = 0
        self.text_input = styled_input(multiline=True, height=84, script=True)
        self.text_input.max_chars = MAX_CHARS
        self.text_input.outer_scroll = self.scroll
        self.text_input.limit_callback = self._text_limit_reached
        self.text_input.text = self.full_script_text
        self.text_input.bind(text=self._on_script_changed)
        self.text_input.bind(focus=self._on_script_focus)
        card.add_widget(self.text_input)
        self.counter_label = make_label(
            "", height=18, color=MUTED, font_size="9sp", halign="right"
        )
        card.add_widget(self.counter_label)
        self.text_status_label = make_label("", height=0, color=GREEN, font_size="9sp")
        self.text_status_label.opacity = 0
        self._counter_trigger = Clock.create_trigger(self._update_counter, 0.25)

    def _build_voice_card(self) -> None:
        card = self._new_card(220)
        card.padding = (dp(12), dp(8))
        card.spacing = dp(2)
        card.border_color = (0.38, 0.20, 0.70, 1)
        self.voice_card = card
        header = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        voice_header_icon = Image(
            source=ui_icon("waveform"),
            fit_mode="contain",
            size_hint=(None, None),
            size=(dp(24), dp(24)),
        )
        voice_header_icon.theme_role = "fixed_light"
        self.voice_studio_label = make_label("", height=32, font_size="16sp", bold=True)
        self.refresh_button = StyledButton(
            size_hint=(None, None),
            size=(dp(86), dp(34)),
            fill_color=FIELD,
            border_color=BORDER,
            font_size="10sp",
        )
        self.refresh_button.bind(on_release=lambda *_: self.refresh_voices(force_catalog=True))
        header.add_widget(voice_header_icon)
        header.add_widget(self.voice_studio_label)
        card.add_widget(header)

        # Keep all compatible voices in one catalogue. Source/engine names are
        # internal and no longer occupy a confusing selector in the UI.
        self.voice_source_label = make_label("", height=0, color=MUTED)
        self.voice_source_label.opacity = 0
        self.voice_source_label.disabled = True
        self.voice_source_spinner = styled_spinner()
        self.voice_source_spinner.height = 0
        self.voice_source_spinner.opacity = 0
        self.voice_source_spinner.disabled = True
        self.voice_source_spinner.bind(text=self._on_voice_source)
        self._bind_spinner_menu(self.voice_source_spinner)

        self.speech_language_label = make_label("", height=0, color=MUTED)
        self.speech_language_label.opacity = 0
        self.speech_language_spinner = styled_spinner()
        self.speech_language_spinner.height = dp(34)
        self.speech_language_spinner.bind(text=self._on_speech_language)
        self._bind_spinner_menu(self.speech_language_spinner)
        card.add_widget(self.speech_language_spinner)

        self.voice_model_label = make_label("", height=0, color=MUTED)
        self.voice_model_label.opacity = 0
        hero = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(9))
        wave = Image(
            source=ui_icon("waveform"),
            fit_mode="contain",
            size_hint=(None, None),
            size=(dp(64), dp(64)),
        )
        wave.theme_role = "fixed_light"
        hero.add_widget(wave)
        voice_stack = BoxLayout(orientation="vertical", spacing=dp(3))
        self.voice_spinner = styled_spinner()
        self.voice_spinner.height = dp(48)
        self.voice_spinner.font_size = "15sp"
        self.voice_spinner.preview_callback = self.preview_voice_choice
        self.voice_spinner.bind(text=self._on_voice_selected)
        self._bind_spinner_menu(self.voice_spinner)
        self.voice_meta_label = make_label("", height=22, color=MUTED, font_size="10sp")
        voice_stack.add_widget(self.voice_spinner)
        voice_stack.add_widget(self.voice_meta_label)
        hero.add_widget(voice_stack)
        card.add_widget(hero)

        self.voice_preview_hint_label = make_label(
            "", height=0, color=MUTED, font_size="9sp", halign="center"
        )
        self.voice_preview_hint_label.opacity = 0
        self.model_status_label = make_label("", height=24, color=MUTED, font_size="10sp")
        self.model_progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(12))

        first_actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.model_download_row = first_actions
        self.model_download_button = StyledButton(
            fill_color=BLUE, border_color=BLUE, role="primary", font_size="11sp"
        )
        self.model_download_button.bind(on_release=lambda *_: self.start_model_download())
        self.model_stop_button = StyledButton(
            fill_color=FIELD, border_color=RED, color=RED, role="danger", font_size="11sp"
        )
        self.model_stop_button.bind(on_release=lambda *_: self.stop_model_download())
        first_actions.add_widget(self.model_download_button)
        first_actions.add_widget(self.model_stop_button)

        second_actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.model_manage_row = second_actions
        self.model_favorite_button = StyledButton(
            fill_color=FIELD, border_color=BORDER, role="secondary", font_size="10sp"
        )
        self.model_favorite_button.bind(on_release=lambda *_: self.toggle_voice_favorite())
        self.model_delete_button = StyledButton(
            fill_color=FIELD, border_color=RED, color=RED, role="danger", font_size="10sp"
        )
        self.model_delete_button.bind(on_release=lambda *_: self.confirm_remove_model())
        second_actions.add_widget(self.model_favorite_button)
        second_actions.add_widget(self.model_delete_button)

        self.cloud_test_button = IconActionButton(
            size_hint_y=None,
            height=dp(36),
            icon_source=ui_icon("microphone"),
            icon_size=dp(31),
            fill_color=FIELD,
            border_color=BLUE,
            color=TEXT,
            role="secondary",
            font_size="12sp",
        )
        self.cloud_test_button.bind(on_release=lambda *_: self.test_cloud_connection())
        card.add_widget(self.cloud_test_button)

        self.elevenlabs_key_input = styled_input(multiline=False, height=0)
        self.elevenlabs_key_input.password = True
        self.elevenlabs_key_input.text = self.elevenlabs_api_key
        self.elevenlabs_key_input.opacity = 0
        self.elevenlabs_key_input.disabled = True
        self.elevenlabs_key_input.bind(text=self._on_elevenlabs_key_changed)
        card.add_widget(self.elevenlabs_key_input)

        card.add_widget(self.voice_preview_hint_label)
        card.add_widget(self.model_status_label)
        card.add_widget(self.model_progress)
        card.add_widget(first_actions)
        card.add_widget(second_actions)

    def _cleanup_legacy_voice_verification_async(self) -> None:
        """Recover storage used by the retired speaker/ASR verification pack."""
        def worker() -> None:
            try:
                removed = cleanup_legacy_verification_data(self.user_data_dir)
                log_event(
                    "legacy_voice_verification_cleanup_complete",
                    removed=removed,
                )
            except Exception as error:
                # Cleanup is a migration convenience and must never block app UI.
                log_exception("legacy_voice_verification_cleanup", error)

        threading.Thread(
            target=worker,
            name="bm-legacy-verification-cleanup",
            daemon=True,
        ).start()

    def _build_voice_clone_card(self) -> None:
        card = self._new_card(86)
        card.padding = (dp(12), dp(9))
        card.spacing = dp(4)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        icon = Image(
            source=ui_icon("microphone"),
            fit_mode="contain",
            size_hint=(None, None),
            size=(dp(34), dp(34)),
        )
        icon.theme_role = "fixed_light"
        labels = BoxLayout(orientation="vertical", spacing=0)
        self.voice_clone_title_label = make_label("", height=24, font_size="14sp", bold=True)
        self.voice_clone_hint_label = make_label("", height=18, font_size="9sp", color=MUTED)
        labels.add_widget(self.voice_clone_title_label)
        labels.add_widget(self.voice_clone_hint_label)
        self.voice_clone_open_button = StyledButton(
            size_hint=(None, None),
            size=(dp(82), dp(38)),
            fill_color=FIELD,
            border_color=BLUE,
            role="secondary",
            font_size="10sp",
        )
        self.voice_clone_open_button.bind(on_release=lambda *_: self._open_voice_clone_popup())
        row.add_widget(icon)
        row.add_widget(labels)
        row.add_widget(self.voice_clone_open_button)
        card.add_widget(row)
        self.voice_clone_card_status = make_label("", height=22, font_size="9sp", color=MUTED)
        card.add_widget(self.voice_clone_card_status)

    def _open_voice_clone_popup(self) -> None:
        if self.voice_consent_popup is not None:
            try:
                self.voice_consent_popup.dismiss()
            except Exception:
                pass

        root = BoxLayout(
            orientation="vertical",
            padding=(dp(12), dp(10)),
            spacing=dp(8),
        )
        popup = Popup(
            title="",
            content=root,
            size_hint=(0.96, 0.90),
            auto_dismiss=False,
            separator_height=0,
            background_color=CARD,
            overlay_color=(0, 0, 0, 0.82),
            title_size="1sp",
        )
        self.voice_consent_popup = popup

        header = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.clone_wizard_title_label = make_label("", height=42, font_size="18sp", bold=True)
        self.clone_wizard_close_button = StyledButton(
            text="×",
            size_hint=(None, None),
            size=(dp(44), dp(42)),
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
            font_size="20sp",
        )
        self.clone_wizard_close_button.bind(on_release=lambda *_: popup.dismiss())
        header.add_widget(self.clone_wizard_title_label)
        header.add_widget(self.clone_wizard_close_button)
        root.add_widget(header)

        steps = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.clone_step_buttons = []
        for _index in range(2):
            chip = StyledButton(
                text="",
                size_hint_y=None,
                height=dp(36),
                fill_color=FIELD,
                border_color=BORDER,
                role="secondary",
                font_size="9sp",
            )
            self.clone_step_buttons.append(chip)
            steps.add_widget(chip)
        root.add_widget(steps)

        self.clone_page_container = BoxLayout()
        root.add_widget(self.clone_page_container)

        # Page 1: one legal attestation and one fresh microphone recording.
        # There is no gallery upload, speaker/ASR model, or verification replay.
        self.clone_page_sample = Card(
            orientation="vertical",
            padding=(dp(12), dp(12)),
            spacing=dp(8),
        )
        self.clone_info_label = make_label(
            "", height=58, font_size="11sp", color=MUTED
        )
        self.clone_page_sample.add_widget(self.clone_info_label)
        self.clone_language_label = make_label("", height=24, font_size="10sp", color=MUTED)
        self.clone_page_sample.add_widget(self.clone_language_label)
        self.clone_language_spinner = styled_spinner()
        self.clone_language_spinner.height = dp(42)
        self.clone_language_spinner.bind(text=self._on_clone_reference_language)
        self._bind_spinner_menu(self.clone_language_spinner)
        self.clone_page_sample.add_widget(self.clone_language_spinner)
        self.clone_consent_button = StyledButton(
            size_hint_y=None,
            height=dp(48),
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
            font_size="10sp",
        )
        self.clone_consent_button.bind(on_release=lambda *_: self._toggle_voice_clone_consent())
        self.clone_page_sample.add_widget(self.clone_consent_button)
        self.clone_legal_notice_label = make_label(
            "", height=86, font_size="8sp", color=MUTED
        )
        self.clone_page_sample.add_widget(self.clone_legal_notice_label)

        permission_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(7))
        self.clone_permission_status = make_label("", height=44, font_size="9sp", color=MUTED)
        self.clone_permission_button = StyledButton(
            size_hint=(None, None),
            size=(dp(142), dp(42)),
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
            font_size="8sp",
        )
        self.clone_permission_button.bind(
            on_release=lambda *_: self._microphone_permission_button_pressed()
        )
        permission_row.add_widget(self.clone_permission_status)
        permission_row.add_widget(self.clone_permission_button)
        self.clone_page_sample.add_widget(permission_row)
        self.clone_challenge_title = make_label("", height=28, font_size="14sp", bold=True)
        self.clone_page_sample.add_widget(self.clone_challenge_title)
        self.clone_challenge_label = make_label(
            "", height=82, font_size="11sp", color=TEXT, halign="center"
        )
        self.clone_page_sample.add_widget(self.clone_challenge_label)
        self.clone_no_playback_label = make_label(
            "", height=46, font_size="8sp", color=MUTED, halign="center"
        )
        self.clone_page_sample.add_widget(self.clone_no_playback_label)
        self.clone_start_button = StyledButton(
            size_hint_y=None,
            height=dp(48),
            fill_color=BLUE,
            border_color=BLUE,
            role="primary",
            font_size="11sp",
        )
        self.clone_start_button.bind(on_release=lambda *_: self._start_voice_clone_challenge())
        self.clone_page_sample.add_widget(self.clone_start_button)
        self.clone_result_label = make_label(
            "", height=48, font_size="10sp", color=MUTED, halign="center"
        )
        self.clone_page_sample.add_widget(self.clone_result_label)
        self.clone_page_sample.add_widget(BoxLayout())
        # Small phones can scroll the legal copy and prompt without any
        # control being compressed or hidden under the footer.
        self.clone_page_sample.size_hint_y = None
        self.clone_page_sample.height = dp(660)
        self.clone_page_sample_scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
        )
        self.clone_page_sample_scroll.add_widget(self.clone_page_sample)

        # Page 2: the real clone engine is a separate one-time install and is
        # shown only after a fresh microphone sample and attestation are saved.
        self.clone_page_ready = Card(
            orientation="vertical",
            padding=(dp(12), dp(12)),
            spacing=dp(8),
        )
        self.clone_ready_hint = make_label("", height=58, font_size="11sp", color=MUTED)
        self.clone_page_ready.add_widget(self.clone_ready_hint)
        self.clone_engine_title = make_label("", height=28, font_size="14sp", bold=True)
        self.clone_page_ready.add_widget(self.clone_engine_title)
        self.clone_engine_status = make_label("", height=36, font_size="10sp", color=MUTED)
        self.clone_page_ready.add_widget(self.clone_engine_status)
        self.clone_engine_progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(8))
        self.clone_page_ready.add_widget(self.clone_engine_progress)
        self.clone_engine_button = StyledButton(
            size_hint_y=None,
            height=dp(48),
            fill_color=FIELD,
            border_color=BLUE,
            role="secondary",
            font_size="10sp",
        )
        self.clone_engine_button.bind(on_release=lambda *_: self._start_voice_clone_model_download())
        self.clone_page_ready.add_widget(self.clone_engine_button)
        self.clone_billing_status = make_label(
            "", height=44, font_size="9sp", color=MUTED, halign="center"
        )
        self.clone_page_ready.add_widget(self.clone_billing_status)
        billing_actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(7))
        self.clone_purchase_button = StyledButton(
            size_hint_y=None,
            height=dp(42),
            fill_color=BLUE,
            border_color=BLUE,
            role="primary",
            font_size="9sp",
        )
        self.clone_purchase_button.bind(on_release=lambda *_: self._launch_clone_purchase())
        self.clone_restore_button = StyledButton(
            size_hint_y=None,
            height=dp(42),
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
            font_size="8sp",
        )
        self.clone_restore_button.bind(on_release=lambda *_: self._restore_clone_purchase())
        billing_actions.add_widget(self.clone_purchase_button)
        billing_actions.add_widget(self.clone_restore_button)
        self.clone_page_ready.add_widget(billing_actions)
        self.clone_policy_label = make_label(
            "", height=64, font_size="8sp", color=MUTED, halign="center"
        )
        self.clone_page_ready.add_widget(self.clone_policy_label)
        self.clone_page_ready.add_widget(BoxLayout())

        footer = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.clone_wizard_back_button = StyledButton(
            size_hint_y=None,
            height=dp(46),
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
            font_size="10sp",
        )
        self.clone_wizard_back_button.bind(
            on_release=lambda *_: self._set_clone_wizard_step(self.clone_wizard_step - 1)
        )
        self.clone_wizard_next_button = StyledButton(
            size_hint_y=None,
            height=dp(46),
            fill_color=BLUE,
            border_color=BLUE,
            role="primary",
            font_size="10sp",
        )
        self.clone_wizard_next_button.bind(on_release=lambda *_: self._clone_wizard_next())
        footer.add_widget(self.clone_wizard_back_button)
        footer.add_widget(self.clone_wizard_next_button)
        root.add_widget(footer)

        has_profile = self.voice_clone_models.has_profile()
        self.clone_wizard_step = 2 if has_profile else 1

        def dismissed(*_args) -> None:
            self.voice_consent_popup = None
            if self._active_popup is popup:
                self._active_popup = None
            self.pending_microphone_action = ""
            self.admob_manager.suspend_banners(False)
            Clock.schedule_once(self._sync_admob_banners, 0)

        popup.bind(on_dismiss=dismissed)
        self._active_popup = popup
        self.admob_manager.suspend_banners(True)
        self._refresh_voice_clone_ui()
        popup.open()
        Clock.schedule_once(self._sync_admob_banners, 0)
        # The user explicitly entered the microphone-based cloning flow, so
        # request permission here once instead of silently failing on Record.
        if platform == "android" and not self._has_microphone_permission():
            Clock.schedule_once(lambda _dt: self._request_microphone_permission(""), 0.45)

    def _set_clone_wizard_step(self, step: int) -> None:
        if not hasattr(self, "clone_page_container"):
            return
        self.clone_wizard_step = max(1, min(2, int(step)))
        pages = (self.clone_page_sample_scroll, self.clone_page_ready)
        self.clone_page_container.clear_widgets()
        self.clone_page_container.add_widget(pages[self.clone_wizard_step - 1])
        self._refresh_voice_clone_ui()

    def _clone_wizard_next(self) -> None:
        if self.clone_wizard_step == 1:
            if not self.voice_clone_models.has_profile():
                self._show_message(self.t("clone_consent_required"))
                return
            self._set_clone_wizard_step(2)
            return
        if self.clone_wizard_step == 2:
            if self.voice_consent_popup is not None:
                self.voice_consent_popup.dismiss()

    def _on_clone_reference_language(self, _spinner, display: str) -> None:
        mapping = getattr(self, "clone_language_display_to_code", {})
        code = mapping.get(display)
        if not code or platform == "android":
            return
        if code == self.clone_reference_language:
            return
        self.clone_reference_language = code
        self._save_settings(clone_reference_language=code)
        # A saved reference transcript belongs to the language it was recorded in.
        # Changing this selector affects the next fresh microphone challenge.
        self._refresh_voice_clone_ui()

    def _refresh_voice_clone_ui(self) -> None:
        billing_ui = self.clone_billing.ui_state(self.ui_language)
        if hasattr(self, "voice_clone_title_label"):
            self.voice_clone_title_label.text = f"[b]{self.t('voice_clone')}[/b]"
            desktop_clone_hints = {
                "kk": "Жеке компьютерде қазақша OmniVoice клондау",
                "ru": "Казахское клонирование OmniVoice на личном ПК",
                "en": "Personal-PC Kazakh cloning with OmniVoice",
            }
            self.voice_clone_hint_label.text = (
                self.t("voice_clone_hint")
                if platform == "android"
                else desktop_clone_hints.get(self.ui_language, desktop_clone_hints["en"])
            )
            self.voice_clone_open_button.text = self.t("voice_clone_open")
            has_profile = self.voice_clone_models.has_profile()
            profile_status = (
                self.t("clone_profile_ready")
                if has_profile
                else self.t("clone_reference_missing")
            )
            access_status = (
                billing_ui["message_text"]
                if billing_ui["lifetime_owned"]
                else billing_ui["quota_text"]
            )
            self.voice_clone_card_status.text = f"{profile_status} · {access_status}"
            self.voice_clone_card_status.color = GREEN if has_profile else MUTED
        if self.voice_consent_popup is None or not hasattr(self, "clone_start_button"):
            return
        self.clone_wizard_title_label.text = f"[b]{self.t('clone_wizard_title')}[/b]"
        desktop_clone_steps = {
            "kk": "Құқықтық растауды қабылдап, экрандағы қысқа қазақша сөйлемді микрофонға 5–10 секунд оқыңыз. Дауыс тек осы компьютерде сақталады.",
            "ru": "Примите подтверждение прав и прочитайте короткую казахскую фразу в микрофон 5–10 секунд. Голос хранится только на этом ПК.",
            "en": "Accept the rights attestation and read the short Kazakh prompt for 5–10 seconds. The voice stays on this PC.",
        }
        self.clone_info_label.text = (
            self.t("clone_page1_hint")
            if platform == "android"
            else desktop_clone_steps.get(self.ui_language, desktop_clone_steps["en"])
        )
        self.clone_language_label.text = self.t("clone_sample_language")
        if platform == "android":
            self.clone_language_display_to_code = {self._language_name("en"): "en"}
        else:
            self.clone_language_display_to_code = {
                self._language_name("kk"): "kk",
                self._language_name("ru"): "ru",
                self._language_name("en"): "en",
            }
        self.clone_language_spinner.values = list(self.clone_language_display_to_code)
        selected_clone_label = next(
            (label for label, code in self.clone_language_display_to_code.items() if code == self.clone_reference_language),
            next(iter(self.clone_language_display_to_code), ""),
        )
        if self.clone_language_spinner.text != selected_clone_label:
            self.clone_language_spinner.text = selected_clone_label
        self.clone_language_spinner.disabled = platform == "android" or bool(self.voice_consent_record_purpose)
        self.clone_ready_hint.text = self.t("clone_page3_hint")
        step_keys = ("clone_step_sample", "clone_step_ready")
        for index, button in enumerate(self.clone_step_buttons, start=1):
            button.text = self.t(step_keys[index - 1])
            active = index == self.clone_wizard_step
            complete = index < self.clone_wizard_step
            button.fill_color = BLUE_DARK if active else FIELD
            button.border_color = GREEN if complete else BLUE if active else BORDER
        self.clone_consent_button.text = self.t(
            "clone_consent_on" if self.voice_consent.consent_granted else "clone_consent_off"
        )
        self.clone_consent_button.border_color = GREEN if self.voice_consent.consent_granted else BORDER
        self.clone_consent_button.disabled = bool(self.voice_consent_record_purpose)
        self.clone_legal_notice_label.text = self.t("clone_legal_notice")
        self.clone_no_playback_label.text = self.t("clone_no_playback_notice")
        permission_state = self._microphone_permission_state()
        if permission_state == "granted":
            self.clone_permission_status.text = self.t("clone_permission_ready")
            self.clone_permission_status.color = GREEN
            self.clone_permission_button.text = self.t("clone_permission_ready")
            self.clone_permission_button.disabled = True
            self.clone_permission_button.border_color = GREEN
        elif permission_state == "pending":
            self.clone_permission_status.text = self.t("clone_permission_pending")
            self.clone_permission_status.color = MUTED
            self.clone_permission_button.text = self.t("clone_permission_pending")
            self.clone_permission_button.disabled = True
        else:
            denied = permission_state == "denied"
            self.clone_permission_status.text = self.t(
                "clone_permission_denied" if denied else "clone_permission_action"
            )
            self.clone_permission_status.color = RED if denied else MUTED
            self.clone_permission_button.text = self.t(
                "clone_open_settings" if denied else "clone_permission_action"
            )
            self.clone_permission_button.disabled = False
            self.clone_permission_button.border_color = RED if denied else BLUE
        self.clone_challenge_title.text = f"[b]{self.t('clone_challenge')}[/b]"
        if not self.voice_consent_challenge_id and not self.voice_consent.clone_unlocked:
            self.clone_challenge_label.text = ""
        self.clone_start_button.text = self.t(
            "clone_cancel" if self.voice_consent_record_purpose == "live" else "clone_start"
        )
        self.clone_start_button.disabled = (
            not self.voice_consent.consent_granted
        ) and self.voice_consent_record_purpose != "live"
        has_profile = self.voice_clone_models.has_profile()
        clone_installed = self.voice_clone_models.is_installed()
        clone_active = bool(
            self.voice_clone_model_worker and self.voice_clone_model_worker.is_alive()
        )
        self.clone_engine_title.text = f"[b]{self.t('clone_engine')}[/b]"
        if not clone_active:
            resumed = self.voice_clone_models.resumable_percent()
            self.clone_engine_progress.value = 100 if clone_installed else resumed
            self.clone_engine_status.text = (
                self.t("clone_engine_ready")
                if clone_installed
                else self.t("clone_download_paused", percent=resumed)
                if has_profile and resumed
                else self.t("clone_download_background")
                if has_profile
                else self.t("clone_engine_locked")
            )
        if clone_installed:
            self.clone_engine_button.text = self.t("clone_engine_ready")
        elif platform == "android":
            self.clone_engine_button.text = self.t("clone_engine_download")
        else:
            self.clone_engine_button.text = {
                "kk": "OMNIVOICE МОДЕЛІН ЖҮКТЕУ · ~3.3 ГБ",
                "ru": "СКАЧАТЬ OMNIVOICE · ~3,3 ГБ",
                "en": "DOWNLOAD OMNIVOICE · ~3.3 GB",
            }.get(self.ui_language, "DOWNLOAD OMNIVOICE · ~3.3 GB")
        self.clone_engine_button.disabled = clone_installed or not has_profile or clone_active
        self.clone_billing_status.text = billing_ui["message_text"]
        self.clone_billing_status.color = (
            GREEN if billing_ui["lifetime_owned"] else RED if not billing_ui["can_generate"] else MUTED
        )
        self.clone_purchase_button.text = (
            billing_ui["message_text"]
            if billing_ui["lifetime_owned"]
            else billing_ui["purchase_button_text"]
        )
        self.clone_purchase_button.disabled = not billing_ui["purchase_enabled"]
        self.clone_restore_button.text = billing_ui["restore_button_text"]
        self.clone_restore_button.disabled = bool(billing_ui["lifetime_owned"])
        self.clone_policy_label.text = self.t(
            "clone_private_profile_policy" if has_profile else "clone_raw_audio_policy"
        )
        self.clone_wizard_back_button.text = self.t("clone_back")
        self.clone_wizard_back_button.disabled = (
            self.clone_wizard_step == 1 or bool(self.voice_consent_record_purpose)
        )
        self.clone_wizard_next_button.text = self.t(
            "clone_finish" if self.clone_wizard_step == 2 else "clone_next"
        )
        step_blocked = self.clone_wizard_step == 1 and not has_profile
        self.clone_wizard_next_button.disabled = (
            bool(self.voice_consent_record_purpose) or step_blocked
        )
        self.clone_wizard_close_button.disabled = bool(self.voice_consent_record_purpose)
        self._set_clone_wizard_page_only()

    def _launch_clone_purchase(self) -> None:
        if not self.clone_billing.launch_purchase():
            self._show_message(self.clone_billing.ui_state(self.ui_language)["message_text"])
        self._refresh_voice_clone_ui()

    def _restore_clone_purchase(self) -> None:
        if not self.clone_billing.restore_purchase():
            self._show_message(self.clone_billing.ui_state(self.ui_language)["message_text"])
        self._refresh_voice_clone_ui()

    def _show_clone_paywall(self) -> None:
        state = self.clone_billing.ui_state(self.ui_language)
        actions: list[tuple[str, Callable[[], None]]] = []
        if state["purchase_enabled"]:
            actions.append((state["purchase_button_text"], self._launch_clone_purchase))
        actions.append((state["restore_button_text"], self._restore_clone_purchase))
        actions.append((self.t("close"), lambda: None))
        self._dialog(state["message_text"], actions, title=state["title_text"])

    def _poll_clone_billing(self, _dt=0) -> bool:
        state = self.clone_billing.snapshot()
        if state.event_version != self.clone_billing_event_version:
            self.clone_billing_event_version = state.event_version
            self._refresh_voice_clone_ui()
        return True

    def _set_clone_wizard_page_only(self) -> None:
        if not hasattr(self, "clone_page_container"):
            return
        pages = (self.clone_page_sample_scroll, self.clone_page_ready)
        selected = pages[max(0, min(1, self.clone_wizard_step - 1))]
        if len(self.clone_page_container.children) != 1 or self.clone_page_container.children[0] is not selected:
            self.clone_page_container.clear_widgets()
            self.clone_page_container.add_widget(selected)

    def _toggle_voice_clone_consent(self) -> None:
        self.voice_consent.grant_consent(not self.voice_consent.consent_granted)
        self._refresh_voice_clone_ui()

    def _has_microphone_permission(self) -> bool:
        if platform != "android":
            return bool(
                self.desktop_voice_recorder
                and self.desktop_voice_recorder.available()
            )
        try:
            return bool(self._android_activity().hasMicrophonePermission())
        except Exception as error:
            log_exception("voice_consent_microphone_permission_check", error)
            return False

    def _microphone_permission_state(self) -> str:
        if platform != "android":
            return "granted" if self._has_microphone_permission() else "denied"
        try:
            return str(self._android_activity().microphonePermissionState())
        except Exception as error:
            log_exception("voice_consent_microphone_permission_state", error)
            return "idle"

    def _microphone_permission_button_pressed(self) -> None:
        if platform != "android":
            self._request_microphone_permission("")
            return
        if self._microphone_permission_state() == "denied":
            try:
                self._android_activity().openApplicationSettings()
            except Exception as error:
                log_exception("voice_consent_open_settings", error)
            return
        self._request_microphone_permission("")

    def _request_microphone_permission(self, action: str) -> None:
        if self._has_microphone_permission():
            self._run_pending_microphone_action(action)
            self._refresh_voice_clone_ui()
            return
        if platform != "android":
            self._show_error(self.t("clone_permission_denied"))
            return
        self.pending_microphone_action = action or self.pending_microphone_action
        try:
            self._android_activity().requestMicrophonePermission()
            if self.microphone_permission_poll is None:
                self.microphone_permission_poll = Clock.schedule_interval(
                    self._poll_microphone_permission, 0.25
                )
        except Exception as error:
            log_exception("voice_consent_microphone_permission_request", error)
        self._refresh_voice_clone_ui()

    def _poll_microphone_permission(self, _dt=0):
        state = self._microphone_permission_state()
        if state == "pending":
            self._refresh_voice_clone_ui()
            return True
        if self.microphone_permission_poll is not None:
            try:
                self.microphone_permission_poll.cancel()
            except Exception:
                pass
            self.microphone_permission_poll = None
        action = self.pending_microphone_action
        self.pending_microphone_action = ""
        self._refresh_voice_clone_ui()
        if state == "granted":
            self._run_pending_microphone_action(action)
        return False

    def _run_pending_microphone_action(self, action: str) -> None:
        if action == "live":
            Clock.schedule_once(lambda _dt: self._begin_voice_clone_challenge(), 0)

    def _stop_voice_consent_recording(self) -> None:
        if platform != "android":
            if self.desktop_voice_recorder is not None:
                self.desktop_voice_recorder.stop()
            return
        try:
            self._android_activity().stopVoiceConsentRecording()
        except Exception as error:
            log_exception("voice_consent_record_stop", error)

    def _start_voice_consent_record_poll(self) -> None:
        if self.voice_consent_record_poll is not None:
            try:
                self.voice_consent_record_poll.cancel()
            except Exception:
                pass
        self.voice_consent_record_poll = Clock.schedule_interval(
            self._poll_voice_consent_recording, 0.20
        )

    def _poll_voice_consent_recording(self, _dt=0) -> None:
        try:
            status = (
                json.loads(str(self._android_activity().voiceConsentRecordingStatus()))
                if platform == "android"
                else self.desktop_voice_recorder.status()
            )
        except Exception as error:
            log_exception("voice_consent_record_status", error)
            return
        state = str(status.get("state") or "")
        seconds = float(status.get("duration_seconds") or 0.0)
        if state in {"starting", "recording"}:
            if self.voice_consent_record_purpose == "live" and hasattr(self, "clone_challenge_label"):
                challenge = self.voice_consent.challenge
                remaining = max(0, int(CHALLENGE_SECONDS - seconds + 0.999))
                if challenge:
                    self.clone_challenge_label.text = self.t(
                        "clone_read_now", seconds=remaining, phrase=challenge.phrase
                    )
            return
        if state not in {"ready", "failed"}:
            return
        if self.voice_consent_record_poll is not None:
            self.voice_consent_record_poll.cancel()
            self.voice_consent_record_poll = None
        purpose = self.voice_consent_record_purpose
        self.voice_consent_record_purpose = ""
        cancelled = self.voice_consent_cancel_requested
        self.voice_consent_cancel_requested = False
        if cancelled:
            path = str(status.get("path") or "")
            if path:
                try:
                    if platform == "android":
                        self._android_activity().deleteVoiceConsentAudio(path)
                    else:
                        self.desktop_voice_recorder.delete(path)
                except Exception:
                    pass
            self.voice_consent_challenge_id = ""
            self.voice_consent_live_path = ""
            self._refresh_voice_clone_ui()
            return
        if state == "failed":
            self._refresh_voice_clone_ui()
            self._show_error(self.t("clone_rejected"))
            return
        path = str(status.get("path") or "")
        if purpose == "live":
            self.voice_consent_live_path = path
            self._evaluate_voice_clone_evidence(path, seconds)
        self._refresh_voice_clone_ui()

    def _start_voice_clone_model_download(self) -> None:
        if self.voice_clone_models.is_installed():
            self._refresh_voice_clone_ui()
            return
        if not self.voice_clone_models.has_profile():
            self._show_error(self.t("clone_engine_locked"))
            return
        if self.voice_clone_model_worker and self.voice_clone_model_worker.is_alive():
            return
        self.voice_clone_model_cancel.clear()

        def progress(value: dict[str, object]) -> None:
            Clock.schedule_once(
                lambda _dt, item=dict(value): self._voice_clone_model_progress(item)
            )

        def worker() -> None:
            try:
                self.voice_clone_models.install(
                    progress=progress,
                    cancel_event=self.voice_clone_model_cancel,
                )
                Clock.schedule_once(lambda _dt: self._voice_clone_model_done())
            except VoiceCloneModelCancelled:
                Clock.schedule_once(lambda _dt: self._voice_clone_model_failed(True))
            except Exception as error:
                log_exception("voice_clone_model_install", error)
                Clock.schedule_once(lambda _dt: self._voice_clone_model_failed(False))

        self.voice_clone_model_worker = threading.Thread(target=worker, daemon=True)
        self.voice_clone_model_worker.start()
        self._set_model_download_active(True)
        self._refresh_voice_clone_ui()

    def _voice_clone_model_progress(self, value: dict[str, object]) -> None:
        if not hasattr(self, "clone_engine_progress"):
            return
        percent = int(value.get("percent") or 0)
        stage = str(value.get("stage") or "")
        self.clone_engine_progress.value = percent
        key = (
            "clone_stage_install"
            if stage == "extract"
            else "clone_stage_verify"
            if stage in {"verify", "done"}
            else "clone_stage_download"
        )
        self.clone_engine_status.text = self.t(key, percent=percent)

    def _voice_clone_model_done(self) -> None:
        self.voice_clone_model_worker = None
        self._set_model_download_active(self._model_downloads_active())
        self.voice_source = "all"
        clone_language = "en" if platform == "android" else (
            self.clone_reference_language if self.clone_reference_language in {"kk", "en", "ru"} else "kk"
        )
        self.preferred_language = clone_language
        self.preferred_voice = "clone:verified"
        self._save_settings(
            voice_source="all",
            speech_language=clone_language,
            voice_id="clone:verified",
        )
        self._refresh_voice_clone_ui()
        if self.voice_consent_popup is not None:
            self._set_clone_wizard_step(2)
        self._rebuild_voice_catalog(clone_language)

    def _voice_clone_model_failed(self, cancelled: bool) -> None:
        self.voice_clone_model_worker = None
        self._set_model_download_active(self._model_downloads_active())
        self._refresh_voice_clone_ui()
        if not cancelled:
            self._show_error(self.t("clone_engine_error"))

    def _model_downloads_active(self) -> bool:
        return bool(
            self.voice_clone_model_worker
            and self.voice_clone_model_worker.is_alive()
        )

    def _set_model_download_active(self, active: bool) -> None:
        if platform != "android":
            return
        try:
            self._android_activity().setModelDownloadActive(bool(active))
        except Exception as error:
            log_exception("voice_clone_keep_screen_on", error)

    def _start_voice_clone_challenge(self) -> None:
        if self.voice_consent_record_purpose == "live":
            self.voice_consent_cancel_requested = True
            self.voice_consent.cancel_challenge()
            self._stop_voice_consent_recording()
            return
        if not self.voice_consent.consent_granted:
            self._show_message(self.t("clone_consent_required"))
            return
        if not self._has_microphone_permission():
            self._request_microphone_permission("live")
            return
        self._begin_voice_clone_challenge()

    def _begin_voice_clone_challenge(self) -> None:
        if self.voice_consent_popup is None or self.voice_consent_record_purpose:
            return
        try:
            # Android keeps the zh/en ZipVoice reference. Windows uses the
            # OpenVoice tone converter and accepts a native Kazakh reference.
            challenge_language = (
                "en" if platform == "android" else self.clone_reference_language
            )
            challenge = self.voice_consent.issue_challenge(challenge_language)
            self.voice_consent_challenge_id = challenge.challenge_id
            self.voice_consent_cancel_requested = False
            if platform == "android":
                payload = json.loads(
                    str(self._android_activity().startVoiceConsentRecording(int(CHALLENGE_SECONDS)))
                )
            else:
                capture = Path(self.user_data_dir) / "voice_clone_capture" / "live_reference.wav"
                payload = self.desktop_voice_recorder.start(capture, 9.5)
            if not payload.get("ok"):
                raise RuntimeError(str(payload.get("error") or "recording_failed"))
            self.voice_consent_record_purpose = "live"
            self.voice_consent_capture_started_at = time.time()
            self.clone_result_label.text = ""
            self.clone_challenge_label.text = self.t(
                "clone_read_now", seconds=int(CHALLENGE_SECONDS), phrase=challenge.phrase
            )
            self._start_voice_consent_record_poll()
            self._refresh_voice_clone_ui()
        except Exception as error:
            log_exception("voice_clone_challenge_start", error)
            self._show_error(self.t("clone_rejected"))

    def _evaluate_voice_clone_evidence(self, live_path: str, live_seconds: float) -> None:
        if hasattr(self, "clone_result_label"):
            self.clone_result_label.text = self.t("clone_verifying")
        challenge_id = self.voice_consent_challenge_id
        started_at = self.voice_consent_capture_started_at
        challenge = self.voice_consent.challenge
        challenge_text = challenge.phrase if challenge is not None else ""
        challenge_language = challenge.language if challenge is not None else "en"

        def worker() -> None:
            try:
                audio_quality = inspect_reference_wave(live_path)
                result = self.voice_consent.verify_fresh_reference(
                    challenge_id=challenge_id,
                    capture_source="microphone",
                    capture_started_at=started_at,
                    capture_finished_at=started_at + float(live_seconds),
                    live_duration_seconds=float(live_seconds),
                    reference_sha256=sha256_file(live_path),
                    audio_quality_reason=audio_quality.reason,
                )
                if result.passed:
                    self.voice_clone_models.save_verified_profile(
                        live_path,
                        reference_text=challenge_text,
                        language=challenge_language,
                        consent_receipt=self.voice_consent.consent_receipt(),
                    )
                Clock.schedule_once(lambda _dt, verified=result: self._voice_clone_evidence_done(verified))
            except Exception as error:
                log_exception("voice_clone_evidence", error)
                Clock.schedule_once(lambda _dt: self._voice_clone_evidence_failed())
            finally:
                try:
                    if platform == "android":
                        self._android_activity().deleteVoiceConsentAudio(live_path)
                    else:
                        self.desktop_voice_recorder.delete(live_path)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _voice_clone_evidence_done(self, result) -> None:
        self.voice_consent_challenge_id = ""
        self.voice_consent_live_path = ""
        if hasattr(self, "clone_result_label"):
            if result.passed:
                self.clone_result_label.text = self.t("clone_verified")
                self.clone_result_label.color = GREEN
                try:
                    receipt_path = Path(self.user_data_dir) / "voice_clone_consent.json"
                    receipt_path.write_text(self.voice_consent.receipt_json(), encoding="utf-8")
                except Exception as error:
                    log_exception("voice_clone_receipt", error)
            elif result.reason is VerificationReason.CHALLENGE_EXPIRED:
                self.clone_result_label.text = self.t("clone_expired")
                self.clone_result_label.color = RED
            else:
                self.clone_result_label.text = self.t("clone_rejected")
                self.clone_result_label.color = RED
        self._refresh_voice_clone_ui()
        if result.passed and self.voice_consent_popup is not None:
            self.voice_reference_seconds = float(
                self.voice_consent.reference.duration_seconds
                if self.voice_consent.reference is not None
                else 0.0
            )
            Clock.schedule_once(lambda _dt: self._set_clone_wizard_step(2), 0.65)

    def _voice_clone_evidence_failed(self) -> None:
        self.voice_consent_challenge_id = ""
        self.voice_consent_live_path = ""
        if hasattr(self, "clone_result_label"):
            self.clone_result_label.text = self.t("clone_rejected")
            self.clone_result_label.color = RED
        self._refresh_voice_clone_ui()

    def _build_advanced_toggle(self) -> None:
        card = self._new_card(52)
        card.padding = (dp(12), dp(6))
        row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
        self.advanced_settings_label = make_label(
            "", height=38, font_size="13sp", bold=True
        )
        self.advanced_settings_button = StyledButton(
            size_hint=(None, None), size=(dp(100), dp(38)),
            fill_color=FIELD, border_color=BORDER, role="secondary", font_size="11sp",
        )
        self.advanced_settings_button.bind(
            on_release=lambda *_: self._set_advanced_settings(
                not self.advanced_settings_open
            )
        )
        row.add_widget(self.advanced_settings_label)
        row.add_widget(self.advanced_settings_button)
        card.add_widget(row)

    def _build_audio_card(self) -> None:
        card = self._new_card(474)
        self.audio_settings_card = card
        card.add_widget(self.timecode_button)
        self.refresh_button.size_hint = (1, None)
        self.refresh_button.height = dp(34)
        card.add_widget(self.refresh_button)
        self.audio_settings_label = make_label("", height=30, font_size="16sp", bold=True)
        card.add_widget(self.audio_settings_label)
        self.rate_slider, self.rate_value, self.rate_name = self._slider_group(
            card, -20, 30, "%", 10
        )
        self.pitch_slider, self.pitch_value, self.pitch_name = self._slider_group(
            card, -20, 20, " Hz", 20
        )
        self.volume_slider, self.volume_value, self.volume_name = self._slider_group(
            card, -20, 20, "%", 20
        )
        self.rate_slider.bind(value=self._on_audio_settings_changed)
        self.pitch_slider.bind(value=self._on_audio_settings_changed)
        self.volume_slider.bind(value=self._on_audio_settings_changed)
        self.sentence_pause_label = make_label("", height=24, color=MUTED)
        card.add_widget(self.sentence_pause_label)
        self.pause_spinner = styled_spinner()
        self.pause_spinner.bind(text=self._on_pause_setting)
        self._bind_spinner_menu(self.pause_spinner)
        card.add_widget(self.pause_spinner)
        self.reset_settings_button = StyledButton(
            size_hint_y=None,
            height=dp(40),
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
        )
        self.reset_settings_button.bind(
            on_release=lambda *_: self.reset_audio_settings()
        )
        card.add_widget(self.reset_settings_button)

    def _slider_group(
        self,
        card: Card,
        minimum: int,
        maximum: int,
        suffix: str,
        step: int,
    ):
        row = BoxLayout(size_hint_y=None, height=dp(24))
        name = make_label("", height=24, color=MUTED)
        value = make_label("+0" + suffix, height=24, bold=True, halign="right")
        row.add_widget(name)
        row.add_widget(value)
        card.add_widget(row)
        slider = StableSlider(
            min=minimum,
            max=maximum,
            value=0,
            step=step,
            size_hint_y=None,
            height=dp(34),
            cursor_size=(dp(22), dp(22)),
            value_track=True,
            value_track_width=dp(3),
            value_track_color=BLUE,
        )
        slider.bind(
            value=lambda _slider, current: setattr(
                value, "text", f"{int(current):+d}{suffix}"
            )
        )
        card.add_widget(slider)
        return slider, value, name

    def _build_file_card(self) -> None:
        card = self._new_card(274)
        self.file_settings_card = card
        self.file_settings_label = make_label("", height=30, font_size="16sp", bold=True)
        card.add_widget(self.file_settings_label)
        modes = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.auto_button = StyledButton(
            fill_color=BLUE, border_color=BLUE, role="primary"
        )
        self.manual_button = StyledButton(
            fill_color=FIELD, border_color=BORDER, role="secondary"
        )
        self.auto_button.bind(on_release=lambda *_: self.set_naming_mode("auto"))
        self.manual_button.bind(on_release=lambda *_: self.set_naming_mode("manual"))
        modes.add_widget(self.auto_button)
        modes.add_widget(self.manual_button)
        card.add_widget(modes)
        self.filename_label = make_label("", height=24, color=MUTED)
        card.add_widget(self.filename_label)
        self.filename_input = styled_input(height=50)
        self.filename_input.disabled = True
        card.add_widget(self.filename_input)
        self.downloads_label = make_label("", height=28, color=MUTED, font_size="12sp")
        card.add_widget(self.downloads_label)
        self.copy_log_button = StyledButton(
            size_hint_y=None,
            height=dp(40),
            font_size="11sp",
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
        )
        self.copy_log_button.bind(on_release=lambda *_: self.copy_log())
        card.add_widget(self.copy_log_button)

    def _set_advanced_settings(self, opened: bool, *, save: bool = True) -> None:
        self.advanced_settings_open = bool(opened)
        if hasattr(self, "audio_settings_card"):
            self.audio_settings_card.height = dp(474) if opened else 0
            self.audio_settings_card.opacity = 1 if opened else 0
            self.audio_settings_card.disabled = not opened
        if hasattr(self, "file_settings_card"):
            self.file_settings_card.height = dp(274) if opened else 0
            self.file_settings_card.opacity = 1 if opened else 0
            self.file_settings_card.disabled = not opened
        if hasattr(self, "advanced_settings_button"):
            self.advanced_settings_button.text = self.t(
                "advanced_close" if opened else "advanced_open"
            )
        if save:
            self._save_settings(advanced_settings_open=self.advanced_settings_open)

    def _build_actions(self) -> None:
        self.generate_button_row = BoxLayout(
            size_hint_y=None,
            height=dp(54),
            padding=(dp(2), dp(2)),
        )
        self.generate_button = IconActionButton(
            icon_source=ui_icon("waveform"),
            icon_size=dp(34),
            fill_color=BLUE,
            border_color=(0.72, 0.36, 1.0, 1),
            font_size="15sp",
            role="primary",
        )
        # ScrollView can cancel a release near its lower edge after even a
        # tiny drag. Starting generation on press keeps the primary action
        # reliable on Android while generate_audio() guards duplicate calls.
        self.generate_button.bind(on_press=lambda *_: self.generate_audio())
        self.generate_button_row.add_widget(self.generate_button)
        self.content.add_widget(self.generate_button_row)
        self.status_label = make_label(
            "", height=24, color=MUTED, font_size="10sp", halign="center"
        )
        self.content.add_widget(self.status_label)

        self.generation_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=0,
            opacity=0,
            disabled=True,
            padding=(dp(14), dp(12)),
            spacing=dp(9),
        )
        self.progress = ProgressBar(
            max=100,
            value=0,
            size_hint_y=None,
            height=dp(8),
        )
        self.generation_card.add_widget(self.progress)
        self.progress_details_label = make_label(
            "", height=150, color=MUTED, font_size="11sp"
        )
        self.generation_card.add_widget(self.progress_details_label)
        generation_controls = BoxLayout(
            size_hint_y=None, height=dp(44), spacing=dp(7)
        )
        self.pause_generation_button = StyledButton(
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
        )
        self.resume_generation_button = StyledButton(
            fill_color=FIELD,
            border_color=BORDER,
            role="secondary",
            disabled=True,
        )
        self.stop_generation_button = StyledButton(
            fill_color=FIELD,
            border_color=RED,
            color=RED,
            role="danger",
        )
        self.pause_generation_button.bind(
            on_release=lambda *_: self.pause_generation()
        )
        self.resume_generation_button.bind(
            on_release=lambda *_: self.resume_generation()
        )
        self.stop_generation_button.bind(
            on_release=lambda *_: self.confirm_stop_generation()
        )
        generation_controls.add_widget(self.pause_generation_button)
        generation_controls.add_widget(self.resume_generation_button)
        generation_controls.add_widget(self.stop_generation_button)
        self.generation_card.add_widget(generation_controls)
        self.retry_merge_button = StyledButton(
            size_hint_y=None,
            height=0,
            opacity=0,
            disabled=True,
            fill_color=BLUE,
            border_color=BLUE,
            role="primary",
        )
        self.retry_merge_button.bind(on_release=lambda *_: self.retry_merge())
        self.generation_card.add_widget(self.retry_merge_button)
        self.content.add_widget(self.generation_card)

        self.review_card = Card(
            orientation="vertical",
            size_hint_y=None,
            height=0,
            opacity=0,
            disabled=True,
            padding=(dp(14), dp(12)),
            spacing=dp(9),
        )
        self.review_label = make_label("", height=36, font_size="17sp", bold=True)
        self.review_card.add_widget(self.review_label)
        self.review_slider = StableSlider(
            min=0,
            max=1,
            value=0,
            size_hint_y=None,
            height=dp(38),
            cursor_size=(dp(22), dp(22)),
            value_track=True,
            value_track_width=dp(3),
            value_track_color=BLUE,
        )
        self.review_slider.bind(on_touch_up=self._seek_audio_from_slider)
        self.review_card.add_widget(self.review_slider)
        time_row = BoxLayout(size_hint_y=None, height=dp(22))
        self.review_current_label = make_label(
            "0:00", height=22, color=MUTED, font_size="10sp"
        )
        self.review_total_label = make_label(
            "0:00", height=22, color=MUTED, font_size="10sp", halign="right"
        )
        self.review_time_label = self.review_current_label
        time_row.add_widget(self.review_current_label)
        time_row.add_widget(self.review_total_label)
        self.review_card.add_widget(time_row)
        controls = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(10))
        self.rewind_button = StyledButton(
            size_hint_x=0.75, fill_color=FIELD, border_color=BORDER,
            role="secondary", font_size="13sp"
        )
        self.play_button = IconActionButton(
            text="",
            icon_source=ui_icon("play"),
            icon_centered=1,
            icon_size=dp(52),
            fill_color=BLUE,
            border_color=(0.72, 0.36, 1.0, 1), role="primary"
        )
        self.forward_button = StyledButton(
            size_hint_x=0.75, fill_color=FIELD, border_color=BORDER,
            role="secondary", font_size="13sp"
        )
        self.pause_button = StyledButton(
            text="", size_hint=(None, None), size=(0, 0), opacity=0, disabled=True,
        )
        self.stop_button = StyledButton(
            text="", size_hint=(None, None), size=(0, 0), opacity=0, disabled=True,
        )
        self.rewind_button.bind(on_release=lambda *_: self.seek_audio_relative(-10_000))
        self.play_button.bind(on_release=lambda *_: self.toggle_audio_playback())
        self.forward_button.bind(on_release=lambda *_: self.seek_audio_relative(10_000))
        controls.add_widget(self.rewind_button)
        controls.add_widget(self.play_button)
        controls.add_widget(self.forward_button)
        self.review_card.add_widget(controls)
        decision = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.save_button = IconActionButton(
            icon_source=ui_icon("save"), icon_size=dp(31),
            fill_color=FIELD, border_color=BLUE, color=TEXT, role="secondary"
        )
        self.delete_button = IconActionButton(
            icon_source=ui_icon("trash"), icon_size=dp(31),
            fill_color=FIELD,
            border_color=RED,
            color=RED,
            size_hint_x=0.42,
            role="danger",
        )
        self.save_button.bind(on_release=lambda *_: self.save_audio())
        self.delete_button.bind(on_release=lambda *_: self.confirm_delete())
        decision.add_widget(self.save_button)
        decision.add_widget(self.delete_button)
        self.review_card.add_widget(decision)
        self.content.add_widget(self.review_card)

    def _build_developer_card(self) -> None:
        card = self._new_card(116)
        card.padding = (dp(14), dp(10))
        card.spacing = dp(5)
        self.developer_channel_label = make_label(
            "",
            height=22,
            font_size="14sp",
            bold=True,
            halign="center",
        )
        self.developer_channel_hint_label = make_label(
            "",
            height=18,
            color=MUTED,
            font_size="11sp",
            halign="center",
        )
        self.developer_channel_button = StyledButton(
            size_hint_y=None,
            height=dp(42),
            fill_color=FIELD,
            border_color=BLUE,
            color=BLUE,
            role="secondary",
        )
        self.developer_channel_button.bind(
            on_release=lambda *_: self.open_developer_channel()
        )
        card.add_widget(self.developer_channel_label)
        card.add_widget(self.developer_channel_hint_label)
        card.add_widget(self.developer_channel_button)

    def t(self, key: str, **values) -> str:
        return I18N[self.ui_language][key].format(**values)

    def _has_network_connection(self) -> bool:
        if platform != "android":
            return True
        try:
            from jnius import autoclass

            Context = autoclass("android.content.Context")
            NetworkCapabilities = autoclass("android.net.NetworkCapabilities")
            activity = self._android_activity()
            manager = activity.getSystemService(Context.CONNECTIVITY_SERVICE)
            network = manager.getActiveNetwork() if manager else None
            capabilities = manager.getNetworkCapabilities(network) if manager and network else None
            return bool(
                capabilities
                and capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            )
        except Exception as error:
            log_exception("network_check", error)
            return True

    def _require_network(self) -> bool:
        if self._has_network_connection():
            return True
        self._show_error(self.t("network_required"))
        return False

    def _on_ui_language_picker(self, _picker, selected: str) -> None:
        if getattr(self, "_setting_ui_language_picker", False):
            return
        code = {
            "Қазақша": "kk", "KZ  v": "kk",
            "Русский": "ru", "RU  v": "ru",
            "English": "en", "EN  v": "en",
        }.get(selected)
        if code and code != self.ui_language:
            self.apply_ui_language(code)

    def _refresh_voice_hero(self) -> None:
        if not hasattr(self, "voice_meta_label"):
            return
        language = (getattr(self.speech_language_spinner, "text", "") or "").split(
            "  ·  ", 1
        )[0]
        parts = [part.strip() for part in (self.voice_spinner.text or "").split("·")]
        profile = parts[1] if len(parts) > 1 else self.t("selected_voice")
        self.voice_meta_label.text = "  ·  ".join(
            item for item in (language, profile, self.t("natural_style")) if item
        )

    def _update_flow_steps(self) -> None:
        if not hasattr(self, "flow_step_buttons"):
            return
        has_text = bool(self._script_text().strip())
        has_voice = bool(self._selected_voice_key())
        stage = 3 if self.draft_path and self.draft_path.exists() else 2 if has_text and has_voice else 1
        self.flow_stage = stage
        labels = (self.t("flow_text"), self.t("flow_voice"), self.t("flow_audio"))
        palette = THEMES[self.theme]
        for index, (button, label) in enumerate(zip(self.flow_step_buttons, labels), start=1):
            completed = index < stage
            active = index == stage
            button.text = f"{'OK' if completed else index}  {label}"
            button.fill_color = BLUE_DARK if completed else BLUE if active else palette["field"]
            button.border_color = BLUE if completed or active else palette["border"]
            button.color = (1, 1, 1, 1) if completed or active else palette["muted"]

    def _update_primary_action_state(self) -> None:
        if not hasattr(self, "generate_button"):
            return
        busy = bool(self._ui_busy)
        self.generate_button.disabled = busy or not bool(self._script_text().strip())

    def apply_ui_language(self, language: str) -> None:
        self.ui_language = language if language in I18N else "kk"
        for code, button in self.ui_language_buttons.items():
            selected = code == self.ui_language
            button.fill_color = BLUE if selected else FIELD
            button.border_color = BLUE if selected else BORDER
        self.title_label.text = f"[b]{self.t('app_title')}[/b]"
        self.subtitle_label.text = self.t("app_tagline")
        self.ready_label.text = f"BM Voice Studio · v{__version__} · {self.t('ready')}"
        self.flow_label.text = self.t("studio_flow")
        for title_label, body_label, hint_label in self.ad_slot_labels.values():
            title_label.text = ""
            body_label.text = ""
            hint_label.text = ""
        self.script_label.text = f"[b]{self.t('text_section')}[/b]"
        self.limit_label.text = "1 000 000"
        self.load_text_button.text = self.t("open_txt_compact")
        self.load_excel_button.text = self.t("open_excel_compact")
        self.paste_button.text = self.t("paste_compact")
        self.timecode_button.text = (
            self.t("timecode_on") if self.timecode_mode else self.t("timecode_compact")
        )
        self.clear_text_button.text = self.t("clear_compact")
        self.text_editor_hint_label.text = (
            self.t("timecode_hint") if self.timecode_mode else self.t("text_editor_hint")
        )
        self.voice_studio_label.text = f"[b]{self.t('voice_select')}[/b]"
        self.refresh_button.text = self.t("refresh")
        self.cloud_test_button.text = self.t("preview_compact")
        self.voice_preview_hint_label.text = self.t("voice_preview_hint")
        self.voice_source_label.text = self.t("voice_source")
        self.voice_source_spinner.picker_title = self.t("voice_source")
        source_labels = self._source_labels()
        self.voice_source_spinner.values = list(source_labels)
        self.voice_source_spinner.text = next(
            (label for label, source in source_labels.items() if source == self.voice_source),
            self.t("source_all"),
        )
        self.speech_language_label.text = self.t("speech_language")
        self.speech_language_spinner.picker_title = self.t("speech_language")
        self.voice_model_label.text = self.t("voice_model")
        self.voice_spinner.picker_title = self.t("voice_model")
        self.audio_settings_label.text = f"[b]{self.t('audio_settings')}[/b]"
        self.rate_name.text = self.t("speed")
        self.pitch_name.text = self.t("pitch")
        self.volume_name.text = self.t("volume")
        self.sentence_pause_label.text = self.t("sentence_pause")
        self.pause_spinner.picker_title = self.t("sentence_pause")
        self.reset_settings_button.text = self.t("reset_settings")
        self.file_settings_label.text = f"[b]{self.t('file_settings')}[/b]"
        self.auto_button.text = self.t("auto")
        self.manual_button.text = self.t("manual")
        self.filename_label.text = self.t("filename")
        self.filename_input.hint_text = self.t("filename_hint")
        self.downloads_label.text = self._save_location_hint()
        self.copy_log_button.text = self.t("copy_error_log")
        self.generate_button.text = self.t("generate_studio")
        self.pause_generation_button.text = self.t("pause")
        self.resume_generation_button.text = self.t("resume")
        self.stop_generation_button.text = self.t("stop")
        self.retry_merge_button.text = self.t("retry_merge")
        self.status_label.text = self.t("ready")
        self.review_label.text = f"[b]{self.t('audio_result')}[/b]"
        self.review_label.height = dp(36)
        self.rewind_button.text = self.t("rewind_10")
        self.forward_button.text = self.t("forward_10")
        self.play_button.icon_source = ui_icon("play")
        self.pause_button.text = self.t("pause")
        self.stop_button.text = self.t("stop")
        self.save_button.text = self.t("save_compact")
        self.delete_button.text = self.t("delete_compact")
        self.advanced_settings_label.text = f"[b]{self.t('advanced_settings_compact')}[/b]"
        self.advanced_settings_button.text = self.t(
            "advanced_close" if self.advanced_settings_open else "advanced_open"
        )
        self.developer_channel_label.text = (
            f"[b]{self.t('developer_channel')}[/b]"
        )
        self.developer_channel_hint_label.text = self.t(
            "developer_channel_hint"
        )
        self.developer_channel_button.text = self.t("youtube_open_channel")
        self.theme_button.text = ""
        self._setting_ui_language_picker = True
        try:
            self.ui_language_picker.values = ["Қазақша", "Русский", "English"]
            self.ui_language_picker.picker_title = {
                "kk": "Интерфейс тілі", "ru": "Язык интерфейса", "en": "Interface language"
            }[self.ui_language]
            self.ui_language_picker.text = {
                "kk": "KZ  v", "ru": "RU  v", "en": "EN  v"
            }[self.ui_language]
        finally:
            self._setting_ui_language_picker = False
        self._refresh_pause_spinner()
        self._update_setting_labels()
        self._render_text_status()
        self._apply_voices(self.voices, preserve=True)
        self._refresh_model_controls()
        self._refresh_elevenlabs_key_ui()
        self._refresh_voice_hero()
        self._refresh_voice_clone_ui()
        self._update_counter()
        self._update_flow_steps()
        self._update_primary_action_state()
        self._refresh_selection_colors()
        self._save_settings(ui_language=self.ui_language)

    def _theme_toggle_caption(self) -> str:
        return "LIGHT" if self.theme == "dark" else "DARK"

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.theme == "dark" else "dark")

    def apply_theme(self, theme: str) -> None:
        self.theme = theme if theme in THEMES else "dark"
        palette = THEMES[self.theme]
        Window.clearcolor = palette["bg"]
        self.scroll.bar_color = BLUE
        for widget in self.root_layout.walk():
            if isinstance(widget, Card):
                widget.bg_color = palette["card"]
                widget.border_color = palette["border"]
            elif isinstance(widget, StyledButton):
                if widget.theme_role == "primary":
                    widget.fill_color = BLUE
                    widget.border_color = BLUE
                    widget.color = (1, 1, 1, 1)
                elif widget.theme_role == "success":
                    widget.fill_color = GREEN
                    widget.border_color = GREEN
                    widget.color = (0.03, 0.12, 0.05, 1)
                elif widget.theme_role == "danger":
                    widget.fill_color = palette["field"]
                    widget.border_color = RED
                    widget.color = RED
                else:
                    widget.fill_color = palette["field"]
                    widget.border_color = palette["border"]
                    widget.color = palette["text"]
                widget.disabled_color = (
                    0.46,
                    0.48,
                    0.53,
                    1,
                )
            elif isinstance(widget, TextInput):
                widget.background_color = palette["field"]
                widget.foreground_color = palette["text"]
                widget.disabled_foreground_color = palette["muted"]
                widget.hint_text_color = palette["muted"]
            elif isinstance(widget, Spinner):
                widget.background_color = palette["field"]
                widget.color = palette["text"]
            elif isinstance(widget, Label):
                role = getattr(widget, "theme_role", "text")
                widget.color = (
                    (1, 1, 1, 1)
                    if role == "fixed_light"
                    else palette["muted"]
                    if role == "muted"
                    else GREEN
                    if role == "success"
                    else RED
                    if role == "danger"
                    else palette["text"]
                )
        self._refresh_selection_colors()
        self.theme_button.text = ""
        self._save_settings(theme=self.theme)
        if platform == "android":
            try:
                from android.runnable import run_on_ui_thread
                from jnius import autoclass

                @run_on_ui_thread
                def update_system_ui() -> None:
                    AndroidColor = autoclass("android.graphics.Color")
                    View = autoclass("android.view.View")
                    PythonActivity = autoclass(
                        "org.kivy.android.PythonActivity"
                    )
                    window = PythonActivity.mActivity.getWindow()
                    decor = window.getDecorView()
                    flags = int(decor.getSystemUiVisibility())
                    light_flags = (
                        int(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR)
                        | int(View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR)
                    )
                    if self.theme == "light":
                        flags |= light_flags
                    else:
                        flags &= ~light_flags
                    color_value = AndroidColor.parseColor(
                        "#F2F4F8" if self.theme == "light" else "#080B10"
                    )
                    window.setStatusBarColor(color_value)
                    window.setNavigationBarColor(color_value)
                    decor.setSystemUiVisibility(flags)

                update_system_ui()
            except Exception as error:
                log_exception("apply_system_theme", error)

    def _refresh_selection_colors(self) -> None:
        palette = THEMES[self.theme]
        for code, button in self.ui_language_buttons.items():
            selected = code == self.ui_language
            button.fill_color = BLUE if selected else palette["field"]
            button.border_color = BLUE if selected else palette["border"]
            button.color = (1, 1, 1, 1) if selected else palette["text"]
        self.theme_button.fill_color = palette["field"]
        self.theme_button.border_color = BLUE
        self.theme_button.color = BLUE
        for button, selected in (
            (self.auto_button, self.naming_mode == "auto"),
            (self.manual_button, self.naming_mode == "manual"),
            (self.timecode_button, self.timecode_mode),
        ):
            button.fill_color = BLUE if selected else palette["field"]
            button.border_color = BLUE if selected else palette["border"]
            button.color = (1, 1, 1, 1) if selected else palette["text"]

    def _on_audio_settings_changed(self, *_args) -> None:
        if not hasattr(self, "rate_value"):
            return
        self._update_setting_labels()
        self._save_settings(
            rate=int(self.rate_slider.value),
            pitch=int(self.pitch_slider.value),
            volume=int(self.volume_slider.value),
        )

    def _update_setting_labels(self) -> None:
        if not hasattr(self, "rate_value"):
            return
        rate = int(self.rate_slider.value)
        pitch = int(self.pitch_slider.value)
        volume = int(self.volume_slider.value)
        rate_key = {
            -20: "rate_slow",
            -10: "rate_slight_slow",
            0: "normal",
            10: "rate_slight_fast",
            20: "rate_fast",
            30: "rate_very_fast",
        }[rate]
        pitch_key = {-20: "pitch_low", 0: "normal", 20: "pitch_high"}[pitch]
        volume_key = {
            -20: "volume_quiet",
            0: "normal",
            20: "volume_loud",
        }[volume]
        self.rate_value.text = f"{self.t(rate_key)} · {rate:+d}%"
        self.pitch_value.text = f"{self.t(pitch_key)} · {pitch:+d} Hz"
        self.volume_value.text = f"{self.t(volume_key)} · {volume:+d}%"

    def _refresh_pause_spinner(self) -> None:
        if not hasattr(self, "pause_spinner"):
            return
        self.pause_display_to_ms = {
            self.t("pause_none"): 0,
            self.t("pause_short"): 250,
            self.t("pause_medium"): 500,
            self.t("pause_long"): 800,
        }
        self.pause_spinner.values = list(self.pause_display_to_ms)
        self.pause_spinner.text = next(
            (
                label
                for label, milliseconds in self.pause_display_to_ms.items()
                if milliseconds == getattr(self, "pause_setting_ms", 0)
            ),
            self.t("pause_none"),
        )

    def _on_pause_setting(self, _spinner, display: str) -> None:
        if not hasattr(self, "pause_display_to_ms"):
            return
        selected = self.pause_display_to_ms.get(display, 0)
        if self._selected_voice_key().startswith("sherpa:"):
            self.pause_setting_ms = int(selected)
        elif selected:
            self.pause_setting_ms = 0
            Clock.schedule_once(
                lambda _dt: setattr(self.pause_spinner, "text", self.t("pause_none"))
            )
            self._show_message(self.t("setting_unsupported"))
        else:
            self.pause_setting_ms = 0
        self._save_settings(sentence_pause_ms=self.pause_setting_ms)

    def reset_audio_settings(self) -> None:
        self.rate_slider.value = 0
        self.pitch_slider.value = 0
        self.volume_slider.value = 0
        self.pause_setting_ms = 0
        self._refresh_pause_spinner()
        self._on_audio_settings_changed()

    def _language_name(self, code: str) -> str:
        names = LANGUAGE_NAMES.get(code)
        if names:
            return names[self.ui_language]
        return self.t("other_language")

    def _voice_model_name(self, short_name: str) -> str:
        parts = short_name.split("-")
        locale_size = 3 if len(parts) >= 4 and len(parts[1]) == 4 else 2
        model = "-".join(parts[locale_size:]).removesuffix("Neural")
        localized = VOICE_NAMES.get(model)
        if localized:
            return localized[self.ui_language]
        readable = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", model)
        readable = re.sub(r"[-_]+\d*", " ", readable)
        readable = " ".join(readable.split()).strip()
        return readable.title() or self.t("voice_model")

    def _voice_display(self, voice: dict[str, str]) -> str:
        gender = (
            self.t("gender_female")
            if voice.get("Gender", "").lower() == "female"
            else self.t("gender_male")
        )
        # Language is selected directly above this picker. Repeating it in
        # every row made the mobile sheet look like a list of technical ids.
        return f"{self._voice_model_name(voice['ShortName'])}  ·  {gender}"

    def _apply_voices(self, voices: list[dict[str, str]], preserve: bool = False) -> None:
        previous_code = self.language_display_to_code.get(
            getattr(self.speech_language_spinner, "text", ""), self.preferred_language
        )
        grouped: dict[str, list[dict[str, str]]] = {}
        for voice in voices:
            code = voice["Locale"].split("-", 1)[0].lower()
            grouped.setdefault(code, []).append(voice)
        self.voices_by_language = grouped
        self._rebuild_voice_catalog(previous_code if preserve else self.preferred_language)

    def _source_labels(self) -> dict[str, str]:
        return {
            self.t("source_all"): "all",
            self.t("source_online"): "edge",
            self.t("source_additional"): "sherpa",
        }

    def _selected_voice_key(self) -> str:
        return self.model_display_to_voice.get(self.voice_spinner.text, "")

    def _selected_offline_model(self) -> dict | None:
        key = self._selected_voice_key()
        if not key.startswith("sherpa:"):
            return None
        return self.offline_model_by_id.get(key.split(":", 1)[1])

    def _offline_model_name(self, model: dict) -> str:
        raw_name = str(model.get("name") or "").lower()
        localized = OFFLINE_VOICE_NAMES.get(raw_name)
        if localized:
            return localized[self.ui_language]
        return str(model.get("display_name") or model.get("name") or model.get("id"))

    def _offline_voice_display(self, model: dict) -> str:
        name = self._offline_model_name(model)
        quality_code = str(model.get("quality") or "standard")
        quality_key = f"quality_{quality_code}"
        quality = self.t(quality_key) if quality_key in I18N[self.ui_language] else str(
            model.get("quality_label") or quality_code
        )
        model_id = str(model.get("id") or "")
        tags: list[str] = []
        if f"sherpa:{model_id}" in self.favorite_voices:
            tags.append(self.t("voice_status_favorite"))
        tags.append(
            self.t("voice_status_ready")
            if self.voice_manager.is_installed(model_id)
            else self.t("voice_status_download")
        )
        profile = quality
        suffix = " · " + " · ".join(tags) if tags else ""
        return f"{name}  ·  {profile}{suffix}".strip()

    def _edge_voice_display(self, voice: dict[str, str]) -> str:
        key = f"edge:{voice['ShortName']}"
        tags: list[str] = []
        if key in self.favorite_voices:
            tags.append(self.t("voice_status_favorite"))
        suffix = " · " + " · ".join(tags) if tags else ""
        return self._voice_display(voice) + suffix

    def _elevenlabs_voice_display(self, voice_name: str, voice_id: str) -> str:
        key = f"elevenv3:{voice_id}"
        tags = ["Eleven v3"]
        if key in self.favorite_voices:
            tags.append(self.t("voice_status_favorite"))
        return f"{voice_name}  ·  ElevenLabs  ·  " + " · ".join(tags)

    def _elevenlabs_key_hint(self) -> str:
        return {
            "kk": "ElevenLabs API key · тек осы компьютерде settings.json ішінде сақталады",
            "ru": "ElevenLabs API key · сохраняется только на этом ПК в settings.json",
            "en": "ElevenLabs API key · stored locally in settings.json on this PC",
        }.get(self.ui_language, "ElevenLabs API key")

    def _on_elevenlabs_key_changed(self, _widget, value: str) -> None:
        self.elevenlabs_api_key = str(value or "").strip()
        self._save_settings(elevenlabs_api_key=self.elevenlabs_api_key)

    def _refresh_elevenlabs_key_ui(self) -> None:
        if not hasattr(self, "elevenlabs_key_input"):
            return
        selected = self._selected_voice_key().startswith("elevenv3:")
        self.elevenlabs_key_input.hint_text = self._elevenlabs_key_hint()
        self.elevenlabs_key_input.height = dp(42) if selected else 0
        self.elevenlabs_key_input.opacity = 1 if selected else 0
        self.elevenlabs_key_input.disabled = not selected or self._ui_busy
        if selected and self._selected_offline_model() is None:
            self.voice_card.height = dp(264)

    def _soniox_voice_display(self, voice_name: str) -> str:
        key = f"soniox:{voice_name}"
        gender = self.t("gender_female") if soniox_gender(voice_name) == "female" else self.t("gender_male")
        tags = ["Soniox AI"]
        if key in self.favorite_voices:
            tags.append(self.t("voice_status_favorite"))
        return f"{voice_name}  ·  {gender}  ·  " + " · ".join(tags)

    def _available_language_codes(self) -> list[str]:
        codes: set[str] = set()
        if self.voice_source in ("all", "edge"):
            codes.update(self.voices_by_language)
        if self.voice_source in ("all", "sherpa"):
            codes.update(str(item.get("language") or "") for item in self.offline_catalog)
        if self.voice_source == "all":
            codes.add("kk")  # Soniox web TTS is exposed here for Kazakh.
            if platform != "android":
                codes.update({"kk", "ru", "en"})  # Official Eleven v3 supports these languages.
        codes.discard("")
        priority = {"kk": 0, "ru": 1, "en": 2}
        return sorted(codes, key=lambda code: (priority.get(code, 10), self._language_name(code)))

    def _merge_installed_voice_catalog(self, catalog: list[dict]) -> list[dict]:
        """Never hide an installed model because an online catalog changed."""

        merged = {str(item.get("id") or ""): dict(item) for item in catalog if item.get("id")}
        for item in self.voice_manager.installed_catalog():
            model_id = str(item.get("id") or "")
            if model_id:
                merged.setdefault(model_id, dict(item))
        return list(merged.values())

    def _rebuild_voice_catalog(self, selected_code: str | None = None) -> None:
        codes = self._available_language_codes()
        self.language_display_to_code = {}
        for code in codes:
            online_count = len(self.voices_by_language.get(code, [])) if self.voice_source in ("all", "edge") else 0
            extra_count = sum(
                1 for item in self.offline_catalog
                if item.get("language") == code and self.voice_source in ("all", "sherpa")
            )
            clone_count = int(
                (
                    code == "en"
                    if platform == "android"
                    else code in {"kk", "en", "ru"}
                )
                and self.voice_source == "all"
                and self.voice_clone_models.has_profile()
                and self.voice_clone_models.is_installed()
            )
            soniox_count = len(SONIOX_VOICE_NAMES) if platform != "android" and code == "kk" and self.voice_source == "all" else 0
            elevenlabs_count = len(ELEVENLABS_VOICES) if platform != "android" and code in {"kk", "ru", "en"} and self.voice_source == "all" else 0
            count = online_count + extra_count + clone_count + soniox_count + elevenlabs_count
            self.language_display_to_code[f"{self._language_name(code)}  ·  {count}"] = code
        self.speech_language_spinner.values = list(self.language_display_to_code)
        selected_code = selected_code or self.preferred_language
        if selected_code not in codes and codes:
            selected_code = "kk" if "kk" in codes else codes[0]
        if selected_code in codes:
            label = next(
                label for label, code in self.language_display_to_code.items() if code == selected_code
            )
            self.speech_language_spinner.text = label
            self._load_voice_models(selected_code)
        else:
            self.voice_spinner.values = []
            self.voice_spinner.text = ""
            self.model_display_to_voice = {}
            self._refresh_model_controls()

    def _on_voice_source(self, _spinner, display: str) -> None:
        source = self._source_labels().get(display)
        if not source or source == self.voice_source:
            return
        self.voice_source = source
        self._save_settings(voice_source=source)
        self._rebuild_voice_catalog(self.preferred_language)

    def _on_speech_language(self, _spinner, display: str) -> None:
        code = self.language_display_to_code.get(display)
        if code:
            self.preferred_language = code
            self._save_settings(speech_language=code)
            self._load_voice_models(code)
            self._refresh_voice_hero()

    def _load_voice_models(self, code: str) -> None:
        entries: list[tuple[int, str, str]] = []
        if (
            (
                code == "en"
                if platform == "android"
                else code in {"kk", "en", "ru"}
            )
            and self.voice_source == "all"
            and self.voice_clone_models.has_profile()
            and self.voice_clone_models.is_installed()
        ):
            entries.append((0, self.t("clone_profile_ready"), "clone:verified"))
        if platform != "android" and code in {"kk", "ru", "en"} and self.voice_source == "all":
            for voice_name, voice_id in ELEVENLABS_VOICES:
                key = f"elevenv3:{voice_id}"
                rank = 0 if key in self.favorite_voices else 1
                entries.append((rank, self._elevenlabs_voice_display(voice_name, voice_id), key))
        if platform != "android" and code == "kk" and self.voice_source == "all":
            for voice_name in SONIOX_VOICE_NAMES:
                key = f"soniox:{voice_name}"
                rank = 0 if key in self.favorite_voices else 1
                entries.append((rank, self._soniox_voice_display(voice_name), key))
        if self.voice_source in ("all", "edge"):
            for voice in self.voices_by_language.get(code, []):
                key = f"edge:{voice['ShortName']}"
                rank = 0 if key in self.favorite_voices else 2
                entries.append((rank, self._edge_voice_display(voice), key))
        if self.voice_source in ("all", "sherpa"):
            for model in self.offline_catalog:
                if model.get("language") != code:
                    continue
                if not is_runtime_compatible_model(model):
                    continue
                model_id = str(model.get("id") or "")
                key = f"sherpa:{model_id}"
                featured = model_id in {
                    "vits-piper-kk_KZ-iseke-x_low",
                    "vits-piper-kk_KZ-raya-x_low",
                }
                rank = (
                    0
                    if key in self.favorite_voices or self.voice_manager.is_installed(model_id)
                    else 1
                    if featured
                    else 3
                )
                entries.append((rank, self._offline_voice_display(model), key))
        entries.sort(key=lambda item: (item[0], item[1].casefold()))
        self.model_display_to_voice = {display: key for _rank, display, key in entries}
        self.voice_spinner.values = list(self.model_display_to_voice)
        if not entries:
            self.voice_spinner.text = ""
            self._refresh_model_controls()
            return
        default_voice = {
            "kk": "edge:kk-KZ-DauletNeural",
            "ru": "edge:ru-RU-DmitryNeural",
            "en": "edge:en-US-GuyNeural",
        }.get(code, "")
        selected = next(
            (display for display, key in self.model_display_to_voice.items() if key == self.preferred_voice),
            next(
                (
                    display
                    for display, key in self.model_display_to_voice.items()
                    if key == default_voice
                ),
                entries[0][1],
            ),
        )
        self.voice_spinner.text = selected
        self._on_voice_selected(self.voice_spinner, selected)

    def _on_voice_selected(self, _spinner, display: str) -> None:
        voice_key = self.model_display_to_voice.get(display)
        if not voice_key:
            return
        self.preferred_voice = voice_key
        self._save_settings(voice_id=voice_key)
        is_local = voice_key.startswith(("sherpa:", "clone:"))
        is_soniox = voice_key.startswith("soniox:")
        is_elevenv3 = voice_key.startswith("elevenv3:")
        self.rate_slider.disabled = is_soniox or is_elevenv3
        self.pitch_slider.disabled = is_local or is_soniox or is_elevenv3
        self.volume_slider.disabled = is_soniox or is_elevenv3
        if (not is_local or is_soniox or is_elevenv3) and getattr(self, "pause_setting_ms", 0):
            self.pause_setting_ms = 0
            self._refresh_pause_spinner()
        self._refresh_model_controls()
        self._refresh_elevenlabs_key_ui()
        self._refresh_voice_hero()
        self._update_flow_steps()

    def _refresh_model_controls(self) -> None:
        if not hasattr(self, "model_download_button"):
            return
        key = self._selected_voice_key()
        self.model_progress.value = 0 if not self.active_download_model_id else self.model_progress.value
        self.model_favorite_button.disabled = not bool(key)
        self.model_favorite_button.text = (
            self.t("model_unfavorite") if key in self.favorite_voices else self.t("model_favorite")
        )
        model = self._selected_offline_model()
        active = bool(self.download_worker and self.download_worker.is_alive())
        if not model:
            self.voice_card.height = dp(220)
            self.model_status_label.height = 0
            self.model_status_label.opacity = 0
            self.model_progress.height = 0
            self.model_progress.opacity = 0
            for row in (self.model_download_row, self.model_manage_row):
                row.height = 0
                row.opacity = 0
                row.disabled = True
            self.model_status_label.text = self.t("voice_ready_hint") if key else ""
            self.model_download_button.text = self.t("model_ready")
            self.model_download_button.disabled = True
            self.model_stop_button.text = self.t("model_stop")
            self.model_stop_button.disabled = True
            self.model_delete_button.text = self.t("model_delete")
            self.model_delete_button.disabled = True
            self.cloud_test_button.disabled = not bool(key)
            return
        self.voice_card.height = dp(350)
        self.model_status_label.height = dp(24)
        self.model_status_label.opacity = 1
        self.model_progress.height = dp(12)
        self.model_progress.opacity = 1
        for row in (self.model_download_row, self.model_manage_row):
            row.height = dp(42)
            row.opacity = 1
            row.disabled = False
        model_id = str(model["id"])
        installed = self.voice_manager.is_installed(model_id)
        partial = self.voice_manager.has_partial(model_id)
        if active and self.active_download_model_id == model_id:
            self.model_download_button.text = self.t("model_download")
            self.model_download_button.disabled = True
            self.model_stop_button.disabled = False
        else:
            self.model_download_button.text = (
                self.t("model_ready") if installed else self.t("model_resume") if partial else self.t("model_download")
            )
            self.model_download_button.disabled = installed or active
            self.model_stop_button.disabled = True
        self.model_stop_button.text = self.t("model_stop")
        self.model_delete_button.text = self.t("model_delete")
        self.model_delete_button.disabled = active or not (installed or partial)
        self.cloud_test_button.disabled = active or not installed
        if installed:
            self.model_status_label.text = self.t(
                "model_installed", size=human_size(self.voice_manager.installed_size(model_id))
            )
            if self.active_download_model_id != model_id:
                self.model_progress.value = 100
        elif partial:
            self.model_status_label.text = self.t(
                "model_partial", size=human_size(self.voice_manager.partial_path(model_id).stat().st_size)
            )
        else:
            self.model_status_label.text = self.t("model_not_downloaded", size=human_size(model.get("size")))

    def refresh_voices(self, force_catalog: bool = False) -> None:
        if self.refresh_button.disabled:
            return
        self.refresh_button.disabled = True
        self.status_label.text = self.t("loading_voices")

        def worker() -> None:
            voice_error = None
            try:
                voices = list_voices()
            except Exception as error:
                voice_error = error
                voices = list(self.voices or FALLBACK_VOICES)

            catalog = None
            catalog_error = None
            try:
                if force_catalog or not cache_is_fresh(self.voice_manager.catalog_cache):
                    catalog = fetch_official_catalog()
                    write_catalog_cache(self.voice_manager.catalog_cache, catalog)
                else:
                    catalog = read_cached_catalog(self.voice_manager.catalog_cache)
            except Exception as error:
                catalog_error = error
                catalog = (
                    read_cached_catalog(self.voice_manager.catalog_cache)
                    or self.offline_catalog
                    or fallback_catalog()
                )

            if voice_error:
                log_exception("online_voice_catalog", voice_error)
            Clock.schedule_once(
                lambda _dt: self._voices_loaded(
                    voices, catalog or fallback_catalog(), catalog_error or voice_error
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _voices_loaded(self, voices: list[dict[str, str]], catalog: list[dict], catalog_error=None) -> None:
        self.voices = voices
        self.offline_catalog = self._merge_installed_voice_catalog(
            catalog or fallback_catalog()
        )
        self.offline_model_by_id = {str(item["id"]): item for item in self.offline_catalog}
        self._apply_voices(voices, preserve=True)
        self.refresh_button.disabled = False
        languages = len({str(item.get("language") or "") for item in self.offline_catalog})
        self.status_label.text = self.t(
            "catalog_loaded", online=len(voices), additional=len(self.offline_catalog), languages=languages
        )
        if catalog_error:
            log_exception("official_voice_catalog", catalog_error)

    def start_model_download(self) -> None:
        model = self._selected_offline_model()
        if not model or (self.download_worker and self.download_worker.is_alive()):
            return
        if not self._require_network():
            return
        model_id = str(model["id"])
        if self.voice_manager.is_installed(model_id):
            return
        self.download_cancel_event.clear()
        self.active_download_model_id = model_id
        self.model_progress.value = 0
        self._refresh_model_controls()

        def progress(event: dict) -> None:
            Clock.schedule_once(lambda _dt, item=event: self._model_download_progress(item))

        def worker() -> None:
            try:
                folder = self.voice_manager.download_and_install(
                    model, progress=progress, cancel_event=self.download_cancel_event
                )
                Clock.schedule_once(lambda _dt: self._model_download_done(model, folder))
            except ModelDownloadCancelled:
                Clock.schedule_once(lambda _dt: self._model_download_cancelled())
            except Exception as error:
                Clock.schedule_once(lambda _dt, captured=error: self._model_download_failed(captured))

        self.download_worker = threading.Thread(target=worker, daemon=True)
        self.download_worker.start()

    def _model_download_progress(self, event: dict) -> None:
        stage = str(event.get("stage") or "download")
        if stage == "download":
            percent = int(event.get("percent", 0))
            self.model_progress.value = percent
            self.model_status_label.text = self.t(
                "model_downloading",
                percent=percent,
                done=human_size(event.get("downloaded")),
                total=human_size(event.get("total")),
                speed=human_size(event.get("bytes_per_second")),
            )
        elif stage == "verify":
            self.model_status_label.text = self.t("model_verifying")
        elif stage == "extract":
            self.model_status_label.text = self.t("model_extracting")

    def _model_download_done(self, model: dict, _folder: Path) -> None:
        self.active_download_model_id = ""
        self.download_worker = None
        self.model_progress.value = 100
        key = f"sherpa:{model['id']}"
        self.preferred_voice = key
        self._save_settings(voice_id=key)
        self._load_voice_models(str(model.get("language") or self.preferred_language))
        self.status_label.text = self.t("model_downloaded", name=self._offline_model_name(model))
        self._show_message(self.status_label.text)

    def _model_download_cancelled(self) -> None:
        self.active_download_model_id = ""
        self.download_worker = None
        self.status_label.text = self.t("model_download_cancelled")
        self._refresh_model_controls()

    def _model_download_failed(self, error: Exception) -> None:
        self.active_download_model_id = ""
        self.download_worker = None
        log_exception("voice_model_download", error)
        self.status_label.text = self.t("model_download_failed", error=str(error))
        self._refresh_model_controls()
        self._show_error(self.status_label.text)

    def stop_model_download(self) -> None:
        if self.download_worker and self.download_worker.is_alive():
            self.download_cancel_event.set()
            self.model_stop_button.disabled = True

    def confirm_remove_model(self) -> None:
        model = self._selected_offline_model()
        if not model:
            return
        name = self._offline_model_name(model)
        self._confirm(self.t("model_delete_confirm", name=name), self.remove_selected_model)

    def remove_selected_model(self) -> None:
        model = self._selected_offline_model()
        if not model:
            return
        model_id = str(model["id"])
        self.voice_manager.remove(model_id)
        if self.preferred_voice == f"sherpa:{model_id}":
            self.preferred_voice = ""
        self.model_progress.value = 0
        self._load_voice_models(str(model.get("language") or self.preferred_language))
        self.status_label.text = self.t("model_deleted")

    def toggle_voice_favorite(self) -> None:
        key = self._selected_voice_key()
        if not key:
            return
        if key in self.favorite_voices:
            self.favorite_voices.remove(key)
        else:
            self.favorite_voices.add(key)
        self._save_settings(favorite_voices=sorted(self.favorite_voices))
        self._load_voice_models(self.preferred_language)

    def test_cloud_connection(self) -> None:
        voice_key = self._selected_voice_key()
        self._preview_voice_key(voice_key)

    def preview_voice_choice(self, display_name: str) -> None:
        """Preview a picker row without selecting it or dismissing the picker."""

        voice_key = self.model_display_to_voice.get(display_name, "")
        self._preview_voice_key(voice_key)

    def _bundled_voice_preview(self, voice_key: str) -> Path | None:
        """Return a real, small voice sample bundled for instant preview."""

        preview_root = Path(__file__).resolve().parent / "assets" / "voice_previews"
        normalized = str(voice_key or "").lower()
        candidates: tuple[str, ...] = ()
        if "iseke" in normalized:
            candidates = ("iseke.wav",)
        elif "raya" in normalized:
            candidates = ("raya.wav",)
        elif "aigulneural" in normalized:
            candidates = ("aigul.mp3",)
        elif "dauletneural" in normalized:
            candidates = ("daulet.mp3",)
        for filename in candidates:
            path = preview_root / filename
            if path.exists() and path.stat().st_size > 0:
                return path
        return None

    def _play_bundled_voice_preview(self, voice_key: str) -> bool:
        path = self._bundled_voice_preview(voice_key)
        if path is None:
            return False
        try:
            self.player.load(path)
            self.player.play()
            self.play_started = False
            self.status_label.text = self.t("preview_ready")
            return True
        except Exception as error:
            log_exception("bundled_voice_preview", error)
            return False

    def _preview_voice_key(self, voice_key: str) -> None:
        if not voice_key or self._voice_preview_busy:
            return
        if voice_key.startswith("clone:"):
            if not self.voice_clone_models.has_profile() or not self.voice_clone_models.is_installed():
                self._show_error(self.t("clone_engine_error"))
                return
            self._voice_preview_busy = True
            self._test_clone_voice()
            return
        if voice_key.startswith("sherpa:"):
            model_id = voice_key.split(":", 1)[1]
            model = self.offline_model_by_id.get(model_id)
            if not model or not self.voice_manager.is_installed(str(model["id"])):
                if self._play_bundled_voice_preview(voice_key):
                    return
                self._show_error(self.t("download_first"))
                return
            self._voice_preview_busy = True
            self._test_sherpa_voice(model)
            return
        if voice_key.startswith("soniox:"):
            if not self._require_network():
                return
            self._voice_preview_busy = True
            self._test_soniox_voice(voice_key)
            return
        if voice_key.startswith("elevenv3:"):
            if not self._require_network():
                return
            if not self.elevenlabs_api_key:
                self._show_error(self._elevenlabs_key_hint())
                return
            self._voice_preview_busy = True
            self._test_elevenlabs_voice(voice_key)
            return
        if self._play_bundled_voice_preview(voice_key):
            return
        if not self._require_network():
            return
        voice = voice_key.split(":", 1)[1]
        self._voice_preview_busy = True
        self.cloud_test_button.disabled = True
        self.status_label.text = self.t("loading_voices")
        sample = I18N[self.ui_language]["sample"]
        output = Path(self.user_data_dir) / "voice_preview.mp3"
        output.unlink(missing_ok=True)

        def worker() -> None:
            try:
                audio = _synthesize_piece(sample, voice, 0, 0, 0)
                temporary = output.with_suffix(".tmp")
                temporary.write_bytes(audio)
                temporary.replace(output)
                Clock.schedule_once(
                    lambda _dt, path=output: self._cloud_preview_done(path)
                )
            except Exception as error:
                log_exception("cloud_connection_test", error)
                Clock.schedule_once(
                    lambda _dt, captured=error: self._cloud_test_failed(captured)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _test_elevenlabs_voice(self, voice_key: str) -> None:
        self.cloud_test_button.disabled = True
        output = Path(self.user_data_dir) / "elevenv3_voice_preview.mp3"
        output.unlink(missing_ok=True)
        language = self.preferred_language if self.preferred_language in {"kk", "ru", "en"} else "kk"
        sample = I18N.get(language, I18N["kk"])["sample"]
        voice_id = voice_key.split(":", 1)[1] if ":" in voice_key else voice_key

        def worker() -> None:
            try:
                client = ElevenLabsV3TTS(self.elevenlabs_api_key)
                payload = client.synthesize_bytes(sample, voice_id=voice_id, language=language)
                temporary = output.with_suffix(".tmp")
                temporary.write_bytes(payload)
                temporary.replace(output)
                Clock.schedule_once(lambda _dt: self._cloud_preview_done(output))
            except Exception as error:
                log_exception("elevenv3_voice_preview", error)
                Clock.schedule_once(lambda _dt, captured=error: self._cloud_test_failed(captured))

        threading.Thread(target=worker, daemon=True).start()

    def _test_soniox_voice(self, voice_key: str) -> None:
        self.cloud_test_button.disabled = True
        output = Path(self.user_data_dir) / "soniox_voice_preview.mp3"
        output.unlink(missing_ok=True)
        language = self.preferred_language if self.preferred_language else "kk"
        sample = I18N.get(language, I18N["kk"])["sample"]
        voice_name = voice_key.split(":", 1)[1] if ":" in voice_key else "Emma"

        def worker() -> None:
            try:
                payload = self.soniox_tts.synthesize_bytes(sample, voice=voice_name, language=language)
                temporary = output.with_suffix(".tmp")
                temporary.write_bytes(payload)
                temporary.replace(output)
                Clock.schedule_once(lambda _dt: self._cloud_preview_done(output))
            except Exception as error:
                log_exception("soniox_voice_preview", error)
                Clock.schedule_once(lambda _dt, captured=error: self._cloud_test_failed(captured))

        threading.Thread(target=worker, daemon=True).start()

    def _test_clone_voice(self) -> None:
        self.cloud_test_button.disabled = True
        output = Path(self.user_data_dir) / "voice_clone_preview.wav"
        output.unlink(missing_ok=True)
        language = "en" if platform == "android" else (
            self.preferred_language if self.preferred_language in {"kk", "en", "ru"} else "kk"
        )
        sample = I18N.get(language, I18N["kk"])["sample"]

        def worker() -> None:
            activity = None
            try:
                paths = self.voice_clone_models.runtime_paths()
                if platform == "android":
                    activity = self._android_activity()
                    ok = bool(
                        activity.synthesizeZipVoiceToWave(
                            paths["model_dir"],
                            2,
                            sample,
                            paths["reference_wave"],
                            paths["reference_text"],
                            1.0,
                            str(output),
                        )
                    )
                else:
                    get_desktop_omnivoice_engine(paths["model_dir"]).synthesize(
                        text=sample,
                        reference_wave=paths["reference_wave"],
                        reference_text=paths["reference_text"],
                        language=language,
                        rate=0,
                        volume=0,
                        output_path=output,
                    )
                    ok = True
                if not ok:
                    raise RuntimeError("Empty cloned voice preview")
                Clock.schedule_once(lambda _dt: self._sherpa_preview_done(output))
            except Exception as error:
                log_exception("clone_voice_preview", error)
                Clock.schedule_once(
                    lambda _dt, captured=error: self._sherpa_test_failed(captured)
                )
            finally:
                if activity is not None:
                    try:
                        activity.releaseZipVoice()
                    except Exception:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    def _cloud_preview_done(self, path: Path) -> None:
        """Play the actual selected voice sample, matching the studio UX."""

        self._voice_preview_busy = False
        self.cloud_test_button.disabled = False
        try:
            if not path.exists() or path.stat().st_size <= 0:
                raise RuntimeError("Voice preview file is empty")
            self.player.load(path)
            self.player.play()
            self.play_started = False
            self.status_label.text = self.t("preview_ready")
        except Exception as error:
            log_exception("cloud_preview_play", error)
            self._cloud_test_failed(error)

    def _test_sherpa_voice(self, model: dict) -> None:
        self.cloud_test_button.disabled = True
        output = Path(self.user_data_dir) / "voice_preview.wav"
        output.unlink(missing_ok=True)
        sample = I18N[self.ui_language]["sample"]

        def worker() -> None:
            activity = None
            try:
                runtime_ok, runtime_details = sherpa_runtime_diagnostic()
                if not runtime_ok:
                    raise RuntimeError(runtime_details)
                activity = self._android_activity()
                ok = bool(
                    activity.synthesizeSherpaToWave(
                        str(self.voice_manager.model_dir(str(model["id"]))),
                        2,
                        sample,
                        0,
                        1.0,
                        str(output),
                    )
                )
                if not ok:
                    raise RuntimeError("Empty preview")
                Clock.schedule_once(lambda _dt: self._sherpa_preview_done(output))
            except Exception as error:
                log_exception("sherpa_voice_preview", error)
                Clock.schedule_once(
                    lambda _dt, captured=error: self._sherpa_test_failed(captured)
                )
            finally:
                if activity is not None:
                    try:
                        activity.releaseSherpa()
                    except Exception:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    def _sherpa_preview_done(self, path: Path) -> None:
        self._voice_preview_busy = False
        self.cloud_test_button.disabled = False
        try:
            self.player.load(path)
            self.player.play()
            self.status_label.text = self.t("preview_ready")
        except Exception as error:
            log_exception("sherpa_preview_play", error)
            self._sherpa_test_failed(error)

    def _explain_sherpa_error(self, error: Exception) -> str:
        raw = str(error).strip() or type(error).__name__
        lowered = raw.lower()
        if "gelu" in lowered and "tensor(float16)" in lowered:
            return self.t("fp16_runtime_error")
        if "bmsherpattsbridge" in lowered and "classnotfoundexception" in lowered:
            return self.t("bridge_missing")
        if "kotlin" in lowered and ("classnotfound" in lowered or "noclassdeffound" in lowered):
            return self.t("kotlin_missing")
        if "unsatisfiedlinkerror" in lowered or "sherpa-onnx-jni" in lowered:
            return self.t("sherpa_jni_missing")
        return self.t("offline_tts_failed")

    def _sherpa_test_failed(self, error: Exception) -> None:
        self._voice_preview_busy = False
        self.cloud_test_button.disabled = False
        message = f"{self.t('device_test_failed')}\n{self._explain_sherpa_error(error)}"
        self.status_label.text = message
        self._show_error(message)

    def _cloud_test_done(self, audio_size: int) -> None:
        self.cloud_test_button.disabled = False
        self.status_label.text = self.t("cloud_test_ok", bytes=self._number(audio_size))
        self._show_message(self.status_label.text)

    def _cloud_test_failed(self, error: Exception | None = None) -> None:
        self._voice_preview_busy = False
        self.cloud_test_button.disabled = False
        message = self.t("cloud_test_failed")
        if error is not None:
            message = f"{message}\n{explain_tts_error(error, self.ui_language)}"
        self.status_label.text = message
        self._show_error(message)

    def _update_counter(self, *_):
        text = self._script_text()
        if self.timecode_mode:
            try:
                cue_count, spoken, duration = self._timecode_summary()
                self.counter_label.text = self.t(
                    "timecode_counter",
                    cues=self._number(cue_count),
                    chars=self._number(spoken),
                    duration=self._duration(duration),
                )
                self.counter_label.color = THEMES[self.theme]["muted"]
            except TimecodeError:
                self.counter_label.text = self.t("timecode_invalid")
                self.counter_label.color = RED
            return
        chars = len(text)
        limit = self._script_limit()
        spoken = spoken_character_count(text, self.script_source)
        self.counter_label.text = (
            f"{self._number(chars)} / {self._number(limit)}"
            + (f"  ·  {self._number(spoken)}" if spoken != chars else "")
        )
        self.counter_label.color = (
            RED if self.is_manual_over_limit else THEMES[self.theme]["muted"]
        )

    def _script_text(self) -> str:
        return self.full_script_text

    def _script_limit(self) -> int:
        return MAX_CHARS

    def toggle_timecode_mode(self) -> None:
        self.timecode_mode = not self.timecode_mode
        self._save_settings(timecode_mode=self.timecode_mode)
        self.timecode_button.text = (
            self.t("timecode_on") if self.timecode_mode else self.t("timecode_compact")
        )
        self.text_editor_hint_label.text = (
            self.t("timecode_hint") if self.timecode_mode else self.t("text_editor_hint")
        )
        self._refresh_selection_colors()
        self._counter_trigger()
        if self.timecode_mode:
            self._set_text_status("timecode_ready")

    def _timecode_summary(self) -> tuple[int, int, int]:
        cues = parse_timecode_text(self._script_text())
        chars = sum(len(cue.text) for cue in cues)
        duration = max(cue.end_ms for cue in cues)
        return len(cues), chars, duration

    @staticmethod
    def _number(value: int) -> str:
        return f"{value:,}".replace(",", " ")

    def _on_script_changed(self, *_args) -> None:
        if self._setting_script_text:
            self._counter_trigger()
            return
        entered = self.text_input.text
        if len(entered) > MAX_CHARS:
            entered = entered[:MAX_CHARS]
            self._setting_script_text = True
            try:
                self.text_input.text = entered
            finally:
                self._setting_script_text = False
            self._text_limit_reached()
        self.full_script_text = entered
        self.script_source = "manual"
        self.is_manual_over_limit = False
        self._text_status_state = None
        self.text_status_label.text = ""
        log_event(
            "script_changed",
            clipboard_length=0,
            inserted_text_length=0,
            text_input_length=len(self.text_input.text),
            full_script_text_length=len(self.full_script_text),
            source=self.script_source,
        )
        self._counter_trigger()
        self._update_flow_steps()
        self._update_primary_action_state()

    def _text_limit_reached(self) -> None:
        if getattr(self, "_text_limit_popup_pending", False):
            return
        self._text_limit_popup_pending = True
        def show(_dt):
            self._text_limit_popup_pending = False
            self._show_error(self.t("text_limit_reached"))
        Clock.schedule_once(show, 0)

    def _on_script_focus(self, _widget, focused: bool) -> None:
        if focused:
            Clock.schedule_once(
                lambda _dt: self.scroll.scroll_to(
                    self.text_input, padding=dp(18), animate=True
                ),
                0.18,
            )
        Clock.schedule_once(self._sync_admob_banners, 0.2)

    def _set_text_status(self, key: str, **values: str) -> None:
        self._text_status_state = (key, values)
        self._render_text_status()

    def _render_text_status(self) -> None:
        if not hasattr(self, "text_status_label"):
            return
        if not self._text_status_state:
            self.text_status_label.text = ""
            return
        key, values = self._text_status_state
        self.text_status_label.text = self.t(key, **values)

    def _set_script_text(
        self,
        text: str,
        source: str,
        show_warning: bool = True,
    ) -> None:
        if len(text) > MAX_CHARS:
            self._show_error(self.t("over_limit"))
            return
        self._setting_script_text = True
        try:
            self.full_script_text = text
            self.script_source = source
            self.is_manual_over_limit = False
            self.text_input.readonly = False
            self.text_input.text = text
            status_key = (
                "timecode_loaded"
                if self.timecode_mode
                else
                "excel_imported"
                if source == "excel"
                else "text_imported"
                if source == "file"
                else "text_pasted"
            )
            if self.timecode_mode:
                cues = estimate_timecode_cues(text)
                self._set_text_status(
                    status_key,
                    cues=self._number(cues),
                    chars=self._number(len(text)),
                )
            else:
                self._set_text_status(status_key, chars=self._number(len(text)))
        finally:
            self._setting_script_text = False
        log_event(
            "script_loaded",
            clipboard_length=len(text) if source == "clipboard" else 0,
            inserted_text_length=len(text),
            text_input_length=len(self.text_input.text),
            full_script_text_length=len(self.full_script_text),
            source=self.script_source,
        )
        self._counter_trigger()
        self.text_input.scroll_y = 0
        self._update_flow_steps()
        self._update_primary_action_state()
        Clock.schedule_once(
            lambda _dt: self.scroll.scroll_to(
                self.text_input, padding=dp(16), animate=True
            ),
            0.12,
        )
        if show_warning and len(text) > 100_000:
            self._show_message(self.t("long_file_warning"))

    def clear_script(self) -> None:
        self._setting_script_text = True
        try:
            self.full_script_text = ""
            self.script_source = "manual"
            self.is_manual_over_limit = False
            self.source_file_name = ""
            self.text_input.readonly = False
            self.text_input.text = ""
            self._text_status_state = None
            self.text_status_label.text = ""
        finally:
            self._setting_script_text = False
        self._counter_trigger()
        self._update_flow_steps()
        self._update_primary_action_state()

    def paste_large_text(self) -> None:
        if self.paste_button.disabled:
            return
        self.paste_button.disabled = True
        if platform == "android":
            threading.Thread(
                target=self._read_clipboard_worker,
                daemon=True,
            ).start()
            return
        try:
            text, method = clipboard_text_details()
        except Exception as error:
            log_exception("clipboard_read", error)
            self._clipboard_failed()
            return
        self._clipboard_loaded(text, method)

    def _read_clipboard_worker(self) -> None:
        try:
            text, method = clipboard_text_details()
            Clock.schedule_once(
                lambda _dt, value=text, source=method: self._clipboard_loaded(
                    value,
                    source,
                )
            )
        except Exception as error:
            log_exception("android_clipboard_read", error)
            Clock.schedule_once(lambda _dt: self._clipboard_failed())

    def _clipboard_failed(self) -> None:
        self.paste_button.disabled = False
        self._show_error(self.t("clipboard_failed"))

    def _clipboard_loaded(self, text: str, method: str) -> None:
        self.paste_button.disabled = False
        if not text:
            self._show_error(self.t("clipboard_empty"))
            return
        log_event(
            "clipboard_read",
            clipboard_length=len(text),
            method=method,
            source="clipboard",
        )
        self._set_script_text(text, "clipboard")
        if len(text) <= MANUAL_MAX_CHARS:
            self._set_text_status(
                "clipboard_read_ok",
                chars=self._number(len(text)),
                method=method,
            )

    @staticmethod
    def _android_activity():
        from android_activity import get_bm_activity

        try:
            return get_bm_activity()
        except Exception:
            pass
        raise RuntimeError("Android activity is unavailable")

    def open_text_file(self) -> None:
        if platform == "android":
            self._open_android_text_file()
            return
        try:
            selected_path = choose_text_file_path(self.t("choose_text_file"))
        except Exception as error:
            log_exception("desktop_txt_picker", error)
            self._show_error(self.t("text_file_error"))
            return
        if selected_path is None:
            return
        self._load_desktop_path_async(
            selected_path,
            source="file",
            reader=read_text_path,
            error_key="text_file_error",
            button=self.load_text_button,
        )

    def open_spreadsheet_file(self) -> None:
        if platform == "android":
            self._open_android_spreadsheet_file()
            return
        try:
            selected_path = choose_spreadsheet_file_path(
                self.t("choose_spreadsheet_file")
            )
        except Exception as error:
            log_exception("desktop_spreadsheet_picker", error)
            self._show_error(self.t("spreadsheet_file_error"))
            return
        if selected_path is None:
            return
        self._load_desktop_path_async(
            selected_path,
            source="excel",
            reader=read_spreadsheet_path,
            error_key="spreadsheet_file_error",
            button=self.load_excel_button,
        )

    def _load_desktop_path_async(
        self,
        selected_path: Path,
        source: str,
        reader: Callable[[Path], str],
        error_key: str,
        button: Button,
    ) -> None:
        button.disabled = True

        def worker() -> None:
            try:
                text = reader(selected_path)
                Clock.schedule_once(
                    lambda _dt, loaded=text: self._desktop_import_done(
                        loaded,
                        source,
                        selected_path.name,
                        button,
                    )
                )
            except Exception as error:
                log_exception(f"desktop_{source}_import", error)
                Clock.schedule_once(
                    lambda _dt, key=error_key: self._desktop_import_failed(
                        key,
                        button,
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def _desktop_import_done(
        self,
        text: str,
        source: str,
        name: str,
        button: Button,
    ) -> None:
        button.disabled = False
        self.source_file_name = name
        self._set_script_text(text, source)

    def _desktop_import_failed(self, error_key: str, button: Button) -> None:
        button.disabled = False
        self._show_error(self.t(error_key))

    def _open_android_text_file(self) -> None:
        try:
            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            current_activity = self._android_activity()
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("text/*")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
            self.load_text_button.disabled = True
            current_activity.startActivityForResult(intent, TEXT_FILE_REQUEST)
        except Exception as error:
            self.load_text_button.disabled = False
            log_exception("open_android_txt_picker", error)
            self._show_error(self.t("text_file_error"))

    def _open_android_spreadsheet_file(self) -> None:
        try:
            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            current_activity = self._android_activity()
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            # Keep the picker provider-compatible. The importer validates
            # XLSX/CSV content after selection.
            intent.setType("*/*")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
            self.load_excel_button.disabled = True
            current_activity.startActivityForResult(
                intent,
                SPREADSHEET_FILE_REQUEST,
            )
        except Exception as error:
            self.load_excel_button.disabled = False
            log_exception("open_android_spreadsheet_picker", error)
            self._show_error(self.t("spreadsheet_file_error"))

    def _poll_android_activity_result(self, _dt=0) -> None:
        if platform != "android":
            return
        try:
            activity = self._android_activity()
            payload = activity.consumePendingActivityResult()
            if payload is None:
                return
            payload = str(payload)
        except Exception as error:
            log_exception("poll_android_activity_result", error)
            return
        if not payload:
            return
        try:
            request_text, result_text, flags_text, uri_text = payload.split(
                "\n",
                3,
            )
            request_code = int(request_text)
            result_code = int(result_text)
            int(flags_text)
        except Exception as error:
            log_exception("parse_android_activity_result", error)
            return
        if request_code not in (
            TEXT_FILE_REQUEST,
            SPREADSHEET_FILE_REQUEST,
        ):
            return
        button = (
            self.load_text_button
            if request_code == TEXT_FILE_REQUEST
            else self.load_excel_button
        )
        if result_code != -1 or not uri_text:
            button.disabled = False
            return

        def worker() -> None:
            try:
                if request_code == TEXT_FILE_REQUEST:
                    loaded_text = read_android_text_uri(uri_text)
                    source = "file"
                else:
                    loaded_text = read_android_spreadsheet_uri(uri_text)
                    source = "excel"
                display_name = android_uri_display_name(uri_text)
                Clock.schedule_once(
                    lambda _dt,
                    loaded=loaded_text,
                    loaded_source=source,
                    name=display_name: self._android_import_done(
                        loaded,
                        loaded_source,
                        name,
                    )
                )
            except Exception as error:
                log_exception("android_file_import", error)
                error_key = (
                    "text_file_error"
                    if request_code == TEXT_FILE_REQUEST
                    else "spreadsheet_file_error"
                )
                Clock.schedule_once(
                    lambda _dt,
                    key=error_key,
                    detail=str(error): self._android_import_failed(
                        key,
                        detail,
                        button,
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def _android_import_done(self, text: str, source: str, name: str) -> None:
        self.load_text_button.disabled = False
        self.load_excel_button.disabled = False
        self.source_file_name = name
        self._set_script_text(text, source)

    def _android_import_failed(
        self,
        error_key: str,
        detail: str,
        button: Button,
    ) -> None:
        button.disabled = False
        log_event("android_import_user_error", error=detail)
        self._show_error(self.t(error_key))

    def set_naming_mode(self, mode: str) -> None:
        self.naming_mode = mode if mode in ("auto", "manual") else "auto"
        self._refresh_selection_colors()
        self.filename_input.disabled = mode != "manual"
        self._save_settings(naming_mode=self.naming_mode)

    def _filename(self) -> str:
        suffix = ".wav" if (
            (self.draft_path and self.draft_path.suffix.lower() == ".wav")
            or self._selected_voice_key().startswith("sherpa:")
        ) else ".mp3"
        if self.naming_mode == "auto":
            if self.source_file_name:
                source_stem = Path(self.source_file_name).stem
                source_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", source_stem).strip(" ._")
                if source_stem:
                    return f"{source_stem[:70]}_BM_Text_to_Voice{suffix}"
            return time.strftime(f"BM_Text_to_Voice_%Y_%m_%d_%H_%M{suffix}")
        name = self.filename_input.text.strip()
        if not name:
            raise ValueError(self.t("manual_required"))
        for current_suffix in (".mp3", ".wav"):
            if name.lower().endswith(current_suffix):
                name = name[: -len(current_suffix)]
                break
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
        if not name:
            raise ValueError(self.t("manual_required"))
        return f"{name[:100]}{suffix}"

    def copy_log(self) -> None:
        try:
            copied = copy_error_log()
        except Exception as error:
            log_exception("copy_error_log", error)
            copied = False
        self._show_message(self.t("log_copied" if copied else "log_empty"))

    def generate_audio(self) -> None:
        log_event(
            "generate_button_pressed",
            source=self.script_source,
            full_script_text_length=len(self.full_script_text),
            selected_voice=self.model_display_to_voice.get(
                self.voice_spinner.text,
                "",
            ),
        )
        if self.worker and self.worker.is_alive():
            return
        if self.draft_path and self.draft_path.exists():
            self._confirm(self.t("confirm_replace"), self._prepare_generation)
            return
        self._prepare_generation()

    def _prepare_generation(self) -> None:
        if self.is_manual_over_limit:
            self._confirm(self.t("manual_long_warning"), self._start_generation)
            return
        self._start_generation()

    def _recommended_workers(self) -> int:
        if platform != "android":
            return 2
        try:
            from jnius import autoclass

            NetworkCapabilities = autoclass("android.net.NetworkCapabilities")
            Context = autoclass("android.content.Context")
            activity = self._android_activity()
            activity_manager = activity.getSystemService(Context.ACTIVITY_SERVICE)
            if activity_manager is not None and int(activity_manager.getMemoryClass()) <= 128:
                return 1
            manager = activity.getSystemService(Context.CONNECTIVITY_SERVICE)
            network = manager.getActiveNetwork() if manager else None
            capabilities = manager.getNetworkCapabilities(network) if manager and network else None
            if capabilities and capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI):
                return 4
            if capabilities and capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR):
                return 2
        except Exception as error:
            log_exception("detect_worker_count", error)
        return 2

    def _recommended_local_threads(self, engine: str) -> int:
        """Use available ARM cores without loading duplicate TTS engines."""

        maximum = 4 if engine == "clone" else 6
        if platform != "android":
            return min(2, maximum)
        try:
            from jnius import autoclass

            Context = autoclass("android.content.Context")
            Runtime = autoclass("java.lang.Runtime")
            activity = self._android_activity()
            activity_manager = activity.getSystemService(Context.ACTIVITY_SERVICE)
            memory_class = int(activity_manager.getMemoryClass()) if activity_manager else 128
            cores = max(1, int(Runtime.getRuntime().availableProcessors()))
            if memory_class <= 128:
                return 1
            if memory_class <= 192:
                return min(2, maximum)
            if cores >= 8:
                return min(4, maximum)
            if cores >= 6:
                return min(3, maximum)
            return min(2, maximum)
        except Exception as error:
            log_exception("detect_local_tts_threads", error)
            return min(2, maximum)

    def _start_generation(
        self,
        resume: bool = False,
        session_data: dict | None = None,
    ) -> None:
        self.clone_quota_count_pending = False
        if resume and session_data:
            script_path = Path(session_data.get("script_path", ""))
            try:
                text = script_path.read_text(encoding="utf-8").strip()
            except Exception as error:
                log_exception("resume_script_read", error)
                self._show_error(self.t("generation_failed"))
                return
            source = session_data.get("source", "file")
            voice = session_data.get("voice", "")
            engine = session_data.get("engine", voice_engine(str(voice)))
            base_engine = session_data.get(
                "base_engine",
                voice_engine(str(voice)),
            )
            language = session_data.get("language", "kk")
            rate = int(session_data.get("rate", 0))
            pitch = int(session_data.get("pitch", 0))
            volume = int(session_data.get("volume", 0))
            sentence_pause_ms = int(session_data.get("pause_setting", 0))
            source_file_name = session_data.get("source_file_name", "")
            output = Path(session_data["final_output_path"])
            workers = (
                1
                if base_engine in ("sherpa", "clone")
                else 1
                if base_engine in ("soniox", "elevenv3")
                else int(session_data.get("workers", self._recommended_workers()))
            )
            local_threads = int(
                session_data.get(
                    "num_threads",
                    self._recommended_local_threads(str(base_engine)),
                )
            )
            model_id = str(session_data.get("model_id", ""))
            model_dir = Path(session_data.get("model_dir", "")) if model_id else None
            self.rate_slider.value = rate
            self.pitch_slider.value = pitch
            self.volume_slider.value = volume
            self.pause_setting_ms = sentence_pause_ms
            self._refresh_pause_spinner()
        else:
            full_text = self._script_text()
            voice = self._selected_voice_key()
            base_engine = voice_engine(voice)
            if self.timecode_mode:
                try:
                    parse_timecode_text(full_text)
                except TimecodeError:
                    self._show_error(self.t("timecode_invalid"))
                    return
                text = full_text.strip()
                source = "timecode"
                engine = "timecode"
            else:
                try:
                    text = text_for_tts(full_text, self.script_source).strip()
                except ValueError:
                    self._show_error(self.t("txt_too_large" if self.script_source == "file" else "over_limit"))
                    return
                source = self.script_source
                engine = base_engine
            language = self.language_display_to_code.get(
                self.speech_language_spinner.text, self.preferred_language
            )
            rate = 0 if base_engine in ("soniox", "elevenv3") else int(self.rate_slider.value)
            pitch = 0 if base_engine in ("sherpa", "clone", "soniox", "elevenv3") else int(self.pitch_slider.value)
            volume = 0 if base_engine in ("soniox", "elevenv3") else int(self.volume_slider.value)
            sentence_pause_ms = int(self.pause_setting_ms) if base_engine in ("sherpa", "clone") else 0
            source_file_name = self.source_file_name
            workers = (
                1
                if base_engine in ("sherpa", "clone")
                else 1
                if base_engine in ("soniox", "elevenv3")
                else self._recommended_workers()
            )
            local_threads = self._recommended_local_threads(base_engine)
            model_id = voice.split(":", 1)[1] if base_engine == "sherpa" and ":" in voice else ""
            model_dir = self.voice_manager.model_dir(model_id) if model_id else None
            cache = Path(self.user_data_dir) / "drafts"
            cache.mkdir(parents=True, exist_ok=True)
            output = cache / ("review.wav" if base_engine in ("sherpa", "clone") or engine == "timecode" else "review.mp3")
            output.unlink(missing_ok=True)

        if not text:
            self._show_error(self.t("empty_text"))
            return
        if not voice:
            self._show_error(self.t("voice_not_ready"))
            return
        clone_paths: dict[str, str] | None = None
        if base_engine == "clone":
            if not self.clone_billing.can_start_generation():
                self._show_clone_paywall()
                return
            if platform == "android" and language != "en":
                self._show_error(self.t("clone_language_only"))
                return
            try:
                clone_paths = self.voice_clone_models.runtime_paths()
                model_dir = Path(clone_paths["model_dir"])
            except VoiceCloneModelError:
                self._show_error(self.t("clone_engine_error"))
                return
        elif base_engine == "sherpa":
            compatible_id = compatible_model_id(model_id)
            if compatible_id != model_id:
                model_id = compatible_id
                model_dir = self.voice_manager.model_dir(model_id)
                voice = f"sherpa:{model_id}"
                self.preferred_voice = voice
                self._save_settings(voice_id=voice)
                if not self.voice_manager.is_installed(model_id):
                    self._show_error(self.t("fp16_incompatible"))
                    return
            if not model_id or model_dir is None or not self.voice_manager.is_installed(model_id):
                self._show_error(self.t("download_first"))
                return
            runtime_ok, runtime_details = sherpa_runtime_diagnostic()
            if not runtime_ok:
                self._show_error(
                    f"{self.t('device_test_failed')}\n"
                    f"{self._explain_sherpa_error(RuntimeError(runtime_details))}"
                )
                return
        else:
            if not self._require_network():
                return
            if base_engine == "elevenv3" and not self.elevenlabs_api_key:
                self._show_error(self._elevenlabs_key_hint())
                return
        self.clone_quota_count_pending = base_engine == "clone"
        self._delete_draft()
        self.cancel_event.clear()
        self.pause_event.clear()
        self.generation_started_at = time.monotonic()
        self.generation_mode = (
            "timecode_mode" if engine == "timecode" else
            "device_mode" if base_engine in ("sherpa", "clone") else
            "mode_long" if source in FILE_TEXT_SOURCES and len(text) > MANUAL_MAX_CHARS else
            "mode_fast" if workers > 1 else "mode_normal"
        )
        self.current_generation_voice_display = next(
            (display for display, voice_id in self.model_display_to_voice.items() if voice_id == voice),
            self.t("voice_model"),
        )
        self.current_generation_settings = (rate, pitch, volume)
        self.current_generation_engine = engine
        self.current_generation_base_engine = base_engine
        self._set_busy(True)
        self.progress.value = 0
        chunk_total = (
            estimate_timecode_cues(text) if engine == "timecode" else
            estimate_clone_chunks(text) if engine == "clone" else
            estimate_sherpa_chunks(text) if engine == "sherpa" else
            estimate_soniox_chunks(text) if engine == "soniox" else
            estimate_elevenlabs_chunks(text) if engine == "elevenv3" else
            estimate_chunks(text)
        )
        self._progress_update(
            {
                "processed_chars": 0,
                "total_chars": len(text),
                "done": 0,
                "total": chunk_total,
                "percent": 0,
                "eta_seconds": 0,
                "failed_chunks": int((session_data or {}).get("failed_chunks", 0)),
                "retry_status": "",
                "workers": workers,
            }
        )

        def progress(event: dict) -> None:
            Clock.schedule_once(lambda _dt, update=event: self._progress_update(update))

        def worker() -> None:
            try:
                if engine == "timecode":
                    activity_holder = {"activity": None}
                    clone_engine_holder = {"engine": None}

                    def synthesize_wav(piece: str, path: Path) -> None:
                        if base_engine == "clone":
                            if clone_paths is None:
                                raise RuntimeError("Verified clone profile is unavailable")
                            if platform == "android":
                                if activity_holder["activity"] is None:
                                    activity_holder["activity"] = self._android_activity()
                                ok = bool(
                                    activity_holder["activity"].synthesizeZipVoiceToWave(
                                        clone_paths["model_dir"],
                                        local_threads,
                                        piece,
                                        clone_paths["reference_wave"],
                                        clone_paths["reference_text"],
                                        float(max(0.5, min(2.0, 1.0 + int(rate) / 100.0))),
                                        str(path),
                                    )
                                )
                            else:
                                if clone_engine_holder["engine"] is None:
                                    clone_engine_holder["engine"] = get_desktop_omnivoice_engine(
                                        clone_paths["model_dir"]
                                    )
                                clone_engine_holder["engine"].synthesize(
                                    text=piece,
                                    reference_wave=clone_paths["reference_wave"],
                                    reference_text=clone_paths["reference_text"],
                                    language=language,
                                    rate=rate,
                                    volume=volume,
                                    output_path=path,
                                )
                                ok = True
                            if not ok:
                                raise RuntimeError("Voice clone produced an invalid WAV cue")
                            return
                        if base_engine == "sherpa":
                            if activity_holder["activity"] is None:
                                activity_holder["activity"] = self._android_activity()
                            ok = bool(
                                activity_holder["activity"].synthesizeSherpaToWave(
                                    str(Path(model_dir).resolve()),
                                    local_threads,
                                    piece,
                                    0,
                                    float(max(0.5, min(2.0, 1.0 + int(rate) / 100.0))),
                                    str(path),
                                )
                            )
                            if not ok:
                                raise RuntimeError("Sherpa produced an invalid WAV cue")
                            return
                        if base_engine == "elevenv3":
                            voice_id = voice.split(":", 1)[1] if voice.startswith("elevenv3:") else voice
                            payload = ElevenLabsV3TTS(self.elevenlabs_api_key).synthesize_bytes(
                                piece, voice_id=voice_id, language=language
                            )
                            mp3_path = path.with_suffix(".elevenv3.mp3")
                            temporary = mp3_path.with_suffix(".mp3.tmp")
                            temporary.write_bytes(payload)
                            temporary.replace(mp3_path)
                            try:
                                if platform == "android" and activity_holder["activity"] is None:
                                    activity_holder["activity"] = self._android_activity()
                                mp3_to_wav(mp3_path, path, android_activity=activity_holder["activity"])
                            finally:
                                temporary.unlink(missing_ok=True)
                                mp3_path.unlink(missing_ok=True)
                            return
                        if base_engine == "soniox":
                            voice_name = voice.split(":", 1)[1] if voice.startswith("soniox:") else voice
                            payload = self.soniox_tts.synthesize_bytes(
                                piece, voice=voice_name, language=language
                            )
                            mp3_path = path.with_suffix(".soniox.mp3")
                            temporary = mp3_path.with_suffix(".mp3.tmp")
                            temporary.write_bytes(payload)
                            temporary.replace(mp3_path)
                            try:
                                if platform == "android" and activity_holder["activity"] is None:
                                    activity_holder["activity"] = self._android_activity()
                                mp3_to_wav(
                                    mp3_path,
                                    path,
                                    android_activity=activity_holder["activity"],
                                )
                            finally:
                                temporary.unlink(missing_ok=True)
                                mp3_path.unlink(missing_ok=True)
                            return
                        payload = _synthesize_piece(
                            piece,
                            voice.split(":", 1)[1] if voice.startswith("edge:") else voice,
                            rate,
                            pitch,
                            volume,
                        )
                        mp3_path = path.with_suffix(".edge.mp3")
                        temporary = mp3_path.with_suffix(".mp3.tmp")
                        temporary.write_bytes(payload)
                        temporary.replace(mp3_path)
                        try:
                            if platform == "android" and activity_holder["activity"] is None:
                                activity_holder["activity"] = self._android_activity()
                            mp3_to_wav(
                                mp3_path,
                                path,
                                android_activity=activity_holder["activity"],
                            )
                        finally:
                            temporary.unlink(missing_ok=True)
                            mp3_path.unlink(missing_ok=True)

                    try:
                        generate_timecoded_wav(
                            script=text,
                            synthesize_wav=synthesize_wav,
                            output_path=output,
                            session_dir=self.session_dir,
                            source=source,
                            source_file_name=source_file_name,
                            voice=voice,
                            language=language,
                            rate=rate,
                            pitch=pitch,
                            volume=volume,
                            base_engine=base_engine,
                            model_id=model_id,
                            model_dir=str(model_dir or ""),
                            speaker_id=0,
                            num_threads=local_threads,
                            workers=workers,
                            progress=progress,
                            pause_event=self.pause_event,
                            cancel_event=self.cancel_event,
                            resume=resume,
                        )
                    finally:
                        activity = activity_holder.get("activity")
                        if activity is not None:
                            try:
                                if base_engine == "clone":
                                    activity.releaseZipVoice()
                                else:
                                    activity.releaseSherpa()
                            except Exception:
                                pass
                elif engine == "clone":
                    if clone_paths is None:
                        raise RuntimeError("Verified clone profile is unavailable")
                    generate_clone_wav(
                        text=text,
                        model_dir=Path(clone_paths["model_dir"]),
                        reference_wave=Path(clone_paths["reference_wave"]),
                        reference_text=clone_paths["reference_text"],
                        language=language,
                        rate=rate,
                        volume=volume,
                        sentence_pause_ms=sentence_pause_ms,
                        output_path=output,
                        session_dir=self.session_dir,
                        source=source,
                        source_file_name=source_file_name,
                        progress=progress,
                        pause_event=self.pause_event,
                        cancel_event=self.cancel_event,
                        resume=resume,
                        num_threads=local_threads,
                    )
                elif engine == "elevenv3":
                    generate_elevenlabs_mp3(
                        client=ElevenLabsV3TTS(self.elevenlabs_api_key),
                        text=text,
                        voice_key=voice,
                        language=language,
                        output_path=output,
                        session_dir=self.session_dir,
                        source=source,
                        source_file_name=source_file_name,
                        progress=progress,
                        pause_event=self.pause_event,
                        cancel_event=self.cancel_event,
                        resume=resume,
                    )
                elif engine == "soniox":
                    generate_soniox_mp3(
                        client=self.soniox_tts,
                        text=text,
                        voice_key=voice,
                        language=language,
                        output_path=output,
                        session_dir=self.session_dir,
                        source=source,
                        source_file_name=source_file_name,
                        workers=workers,
                        progress=progress,
                        pause_event=self.pause_event,
                        cancel_event=self.cancel_event,
                        resume=resume,
                    )
                elif engine == "sherpa":
                    generate_one_wav(
                        text=text,
                        model_dir=model_dir,
                        model_id=model_id,
                        language=language,
                        rate=rate,
                        pitch=pitch,
                        volume=volume,
                        sentence_pause_ms=sentence_pause_ms,
                        output_path=output,
                        session_dir=self.session_dir,
                        source=source,
                        source_file_name=source_file_name,
                        progress=progress,
                        pause_event=self.pause_event,
                        cancel_event=self.cancel_event,
                        resume=resume,
                        num_threads=local_threads,
                    )
                else:
                    edge_voice = voice.split(":", 1)[1] if voice.startswith("edge:") else voice
                    generate_one_mp3(
                        text=text,
                        voice=edge_voice,
                        language=language,
                        rate=rate,
                        pitch=pitch,
                        volume=volume,
                        sentence_pause_ms=sentence_pause_ms,
                        output_path=output,
                        session_dir=self.session_dir,
                        source=source,
                        source_file_name=source_file_name,
                        workers=workers,
                        progress=progress,
                        pause_event=self.pause_event,
                        cancel_event=self.cancel_event,
                        resume=resume,
                    )
                Clock.schedule_once(lambda _dt: self._generation_done(output))
            except Exception as error:
                Clock.schedule_once(lambda _dt, captured=error: self._generation_failed(captured))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _progress_update(self, event: dict) -> None:
        done = int(event.get("done", 0))
        total = int(event.get("total", 1))
        percent = int(event.get("percent", 0))
        total_chars = int(event.get("total_chars", 0))
        rate, pitch, volume = self.current_generation_settings
        words = max(1, total_chars / 6)
        words_per_minute = max(60, 150 * (1 + rate / 100))
        estimated_seconds = int(words / words_per_minute * 60)
        voice_display = self.current_generation_voice_display
        settings = (
            f"{rate:+d}% · "
            f"{pitch:+d} Hz · "
            f"{volume:+d}%"
        )
        self.progress.value = percent
        self.status_label.text = self.t("generating", done=done, total=total)
        details = self.t(
            "progress_details",
            processed=self._number(int(event.get("processed_chars", 0))),
            total_chars=self._number(total_chars),
            done=done,
            total=total,
            percent=percent,
            eta=self._duration(int(event.get("eta_seconds", 0)) * 1000),
            audio_duration=self._duration(estimated_seconds * 1000),
            mode=self.t(self.generation_mode),
            failed=int(event.get("failed_chunks", 0)),
            retry_status=event.get("retry_status") or "—",
            voice=voice_display,
            settings=settings,
        )
        for phrase in (
            "Соңында бір толық MP3 аудио шығады",
            "В результате получится один полный MP3-файл",
            "The result will be one complete MP3",
        ):
            details = details.replace(phrase, self.t("audio_file_ready"))
        self.progress_details_label.text = details

    def _set_busy(self, busy: bool) -> None:
        self._ui_busy = bool(busy)
        self.generate_button.disabled = busy
        self.refresh_button.disabled = busy
        self.cloud_test_button.disabled = busy
        self.timecode_button.disabled = busy
        self.voice_source_spinner.disabled = busy
        self.speech_language_spinner.disabled = busy
        self.voice_spinner.disabled = busy
        if hasattr(self, "elevenlabs_key_input"):
            self.elevenlabs_key_input.disabled = busy or not self._selected_voice_key().startswith("elevenv3:")
        self.model_download_button.disabled = busy or self.model_download_button.disabled
        self.model_delete_button.disabled = busy or self.model_delete_button.disabled
        self.model_favorite_button.disabled = busy
        if busy:
            self.generation_card.height = dp(250)
            self.generation_card.opacity = 1
            self.generation_card.disabled = False
            self.pause_generation_button.disabled = False
            self.resume_generation_button.disabled = True
            self.stop_generation_button.disabled = False
            self.retry_merge_button.height = 0
            self.retry_merge_button.opacity = 0
            self.retry_merge_button.disabled = True
        else:
            self.timecode_button.disabled = False
            self.voice_source_spinner.disabled = False
            self.speech_language_spinner.disabled = False
            self.voice_spinner.disabled = False
            self._refresh_model_controls()
            self._refresh_elevenlabs_key_ui()
            if self.retry_merge_button.disabled:
                self.generation_card.height = 0
                self.generation_card.opacity = 0
                self.generation_card.disabled = True
        self._update_primary_action_state()

    def cancel_generation(self) -> None:
        self.cancel_event.set()
        self.pause_generation_button.disabled = True
        self.resume_generation_button.disabled = True
        self.stop_generation_button.disabled = True

    def pause_generation(self) -> None:
        if not self.worker or not self.worker.is_alive():
            return
        self.pause_event.set()
        self.pause_generation_button.disabled = True
        self.resume_generation_button.disabled = False
        self.status_label.text = self.t("paused", now="—", total="—")

    def resume_generation(self) -> None:
        if self.worker and self.worker.is_alive():
            self.pause_event.clear()
            self.pause_generation_button.disabled = False
            self.resume_generation_button.disabled = True
            return
        session = load_generation_session(self.session_dir)
        if session:
            self._start_generation(resume=True, session_data=session)

    def confirm_stop_generation(self) -> None:
        self._confirm(self.t("confirm_stop"), self.cancel_generation)

    def retry_merge(self) -> None:
        self.retry_merge_button.disabled = True

        def worker() -> None:
            try:
                session = load_generation_session(self.session_dir) or {}
                output = (
                    retry_timecode_merge_session(self.session_dir)
                    if session.get("engine") == "timecode"
                    else
                    retry_sherpa_merge_session(self.session_dir)
                    if session.get("engine") == "sherpa"
                    else retry_clone_merge_session(self.session_dir)
                    if session.get("engine") == "clone"
                    else retry_merge_session(self.session_dir)
                )
                Clock.schedule_once(lambda _dt: self._generation_done(output))
            except Exception as error:
                Clock.schedule_once(lambda _dt, captured=error: self._generation_failed(captured))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _generation_done(self, path: Path) -> None:
        self._set_busy(False)
        if not path.exists() or path.stat().st_size <= 0:
            self._generation_failed(RuntimeError("Generated audio file is missing or empty."))
            return
        if self.clone_quota_count_pending:
            if not verify_wav_file(path):
                self._generation_failed(RuntimeError("Generated clone audio is not a playable WAV."))
                return
            billing_state = self.clone_billing.record_completed_generation()
            self.clone_quota_count_pending = False
            log_event(
                "voice_clone_generation_counted",
                completed=billing_state.completed_generations,
                remaining=billing_state.remaining_free,
                lifetime_owned=billing_state.lifetime_owned,
            )
            self._refresh_voice_clone_ui()

        self.draft_path = path
        self.progress.value = 100
        self.review_card.height = dp(280)
        self.review_card.opacity = 1
        self.review_card.disabled = False
        self.play_button.disabled = False
        self.pause_button.disabled = False
        self.stop_button.disabled = False

        try:
            self.player.load(path)
            duration = self.player.duration_ms()
            if duration <= 0:
                raise RuntimeError("Audio duration could not be detected.")
            self.review_current_label.text = "0:00"
            self.review_total_label.text = self._duration(duration)
            self.review_slider.max = max(1, duration)
            self.review_slider.value = 0
            self.status_label.text = self.t("audio_ready")
            self._update_flow_steps()
            Clock.schedule_once(
                lambda _dt: self.scroll.scroll_to(
                    self.review_card, padding=dp(18), animate=True
                ),
                0.12,
            )
            Clock.schedule_once(lambda _dt: self.admob_manager.show_interstitial(), 0.25)
        except Exception as error:
            # The final file can be valid even when Android MediaPlayer cannot
            # prepare a preview. Keep Save/Delete available instead of claiming
            # that the internet failed and discarding a completed generation.
            log_exception("final_audio_preview", error)
            self.player.release()
            self.play_button.disabled = True
            self.pause_button.disabled = True
            self.stop_button.disabled = True
            self.review_current_label.text = "—"
            self.review_total_label.text = "—"
            self.review_slider.max = 1
            self.review_slider.value = 0
            self.status_label.text = self.t("audio_ready_no_preview")
            self._show_message(self.status_label.text)

    def _generation_failed(self, error: Exception) -> None:
        self._set_busy(False)
        if not isinstance(error, MergeError):
            self.clone_quota_count_pending = False
        if isinstance(error, CancelledError):
            self.status_label.text = self.t("cancelled")
        elif isinstance(error, MergeError):
            log_exception("merge_audio", error)
            self.status_label.text = self.t("merge_failed")
            self._show_error(self.t("merge_failed"))
            self.generation_card.height = dp(300)
            self.generation_card.opacity = 1
            self.generation_card.disabled = False
            self.retry_merge_button.height = dp(46)
            self.retry_merge_button.opacity = 1
            self.retry_merge_button.disabled = False
        else:
            log_exception("tts_generation", error)
            self.status_label.text = self.t("error")
            engine = getattr(self, "current_generation_engine", "edge")
            base_engine = getattr(self, "current_generation_base_engine", engine)
            if engine == "edge" or (engine == "timecode" and base_engine == "edge"):
                detail = explain_tts_error(error, self.ui_language)
            elif engine == "soniox" or (engine == "timecode" and base_engine == "soniox"):
                detail = str(error).strip() or "Soniox TTS error"
            else:
                detail = self._explain_sherpa_error(error)
            self._show_error(self.t("generation_failed_detail", detail=detail))
            self.generation_card.height = dp(250)
            self.generation_card.opacity = 1
            self.generation_card.disabled = False
            self.pause_generation_button.disabled = True
            self.resume_generation_button.disabled = False
            self.stop_generation_button.disabled = True

    def play_audio(self) -> None:
        if not self.draft_path or not self.draft_path.exists():
            return
        try:
            if self.player.path != self.draft_path.resolve():
                self.player.load(self.draft_path)
            self.player.play()
            self.play_started = True
            self.play_button.icon_source = ui_icon("pause")
        except Exception as error:
            log_exception("play_audio", error)
            self._show_error(self.t("playback_failed"))

    def pause_audio(self) -> None:
        try:
            self.player.pause()
            now = self._duration(self.player.position_ms())
            total = self._duration(self.player.duration_ms())
            self.status_label.text = self.t("paused", now=now, total=total)
            self.play_button.icon_source = ui_icon("play")
        except Exception as error:
            log_exception("pause_audio", error)
            self._show_error(self.t("playback_failed"))

    def stop_audio(self) -> None:
        try:
            self.player.stop()
            self.play_started = False
            self.review_slider.value = 0
            self.status_label.text = self.t("stopped")
            self.play_button.icon_source = ui_icon("play")
        except Exception as error:
            log_exception("stop_audio", error)
            self._show_error(self.t("playback_failed"))

    def toggle_audio_playback(self) -> None:
        if self.player.is_playing():
            self.pause_audio()
        else:
            self.play_audio()

    def seek_audio_relative(self, milliseconds: int) -> None:
        if not self.player.path:
            return
        try:
            self.player.seek_ms(self.player.position_ms() + int(milliseconds))
            self._poll_player(0)
        except Exception as error:
            log_exception("seek_audio_relative", error)
            self._show_error(self.t("playback_failed"))

    def _seek_audio_from_slider(self, slider, touch) -> None:
        if (
            not self._polling_review_slider
            and slider.collide_point(*touch.pos)
            and self.player.path
        ):
            try:
                self.player.seek_ms(int(slider.value))
            except Exception as error:
                log_exception("seek_audio", error)

    @staticmethod
    def _duration(milliseconds: int) -> str:
        seconds = max(0, milliseconds // 1000)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return (
            f"{hours}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes}:{seconds:02d}"
        )

    def _poll_player(self, _dt) -> None:
        if not self.player.path:
            return
        now_ms = self.player.position_ms()
        total_ms = self.player.duration_ms()
        self._polling_review_slider = True
        self.review_slider.max = max(1, total_ms)
        self.review_slider.value = now_ms
        self.review_current_label.text = self._duration(now_ms)
        self.review_total_label.text = self._duration(total_ms)
        self._polling_review_slider = False
        if self.player.is_playing():
            self.play_button.icon_source = ui_icon("pause")
            self.status_label.text = self.t(
                "playing",
                now=self._duration(now_ms),
                total=self._duration(total_ms),
            )
        elif self.play_started and total_ms and now_ms >= total_ms - 500:
            self.play_started = False
            self.play_button.icon_source = ui_icon("play")
            self.status_label.text = self.t("audio_ready")

    def save_audio(self) -> None:
        if not self.draft_path or not self.draft_path.exists():
            return
        try:
            filename = self._filename()
        except ValueError as error:
            self._show_error(str(error))
            return
        self.save_button.disabled = True
        source = self.draft_path
        if platform != "android":
            self.save_button.disabled = False
            try:
                destination_path = choose_save_audio_path(self.t("save"), filename)
            except Exception as error:
                log_exception("desktop_save_picker", error)
                self._show_error(self.t("save_failed"))
                return
            if destination_path is None:
                return
            self.save_button.disabled = True

            def desktop_worker():
                try:
                    destination = save_audio_to_path(source, destination_path)
                    Clock.schedule_once(
                        lambda _dt: self._save_done(destination)
                    )
                except Exception as error:
                    Clock.schedule_once(
                        lambda _dt, captured=error: self._save_failed(captured)
                    )

            threading.Thread(target=desktop_worker, daemon=True).start()
            return

        def worker():
            try:
                destination = save_to_public_audio(source, filename)
                Clock.schedule_once(
                    lambda _dt: self._save_done(destination)
                )
            except Exception as error:
                Clock.schedule_once(
                    lambda _dt, captured=error: self._save_failed(captured)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _save_done(self, destination: str) -> None:
        self.save_button.disabled = False
        # Saving to Downloads/Music creates an independent public copy. Keep
        # the in-app result available for replay and re-save until the user
        # explicitly presses Delete. Deleting it later must never touch the
        # MediaStore/public copy returned in ``destination``.
        self.progress.value = 100
        self.status_label.text = self.t("saved", path=destination)
        self._show_message(self.t("saved", path=destination))

    def _save_failed(self, error: Exception) -> None:
        self.save_button.disabled = False
        log_exception("save_audio", error)
        self.status_label.text = self.t("save_failed")
        self._show_error(self.t("save_failed"))

    def confirm_delete(self) -> None:
        self._confirm(self.t("confirm_delete"), self._delete_draft_with_status)

    def _delete_draft_with_status(self) -> None:
        self._delete_draft()
        self.progress.value = 0
        self.status_label.text = self.t("deleted")

    def _delete_draft(self) -> None:
        self.player.release()
        self.play_started = False
        if self.draft_path:
            self.draft_path.unlink(missing_ok=True)
        self.draft_path = None
        self.review_card.height = 0
        self.review_card.opacity = 0
        self.review_card.disabled = True
        self._update_flow_steps()
        self._update_primary_action_state()

    def open_developer_channel(self) -> None:
        try:
            if platform == "android":
                from jnius import autoclass

                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                intent = Intent(Intent.ACTION_VIEW, Uri.parse(YOUTUBE_CHANNEL_URL))
                PythonActivity.mActivity.startActivity(intent)
            else:
                import webbrowser

                if not webbrowser.open(YOUTUBE_CHANNEL_URL):
                    raise RuntimeError("No browser accepted the YouTube URL")
            log_event("developer_channel_opened", url=YOUTUBE_CHANNEL_URL)
        except Exception as error:
            log_exception("developer_channel_open_failed", error)
            self._show_error(self.t("youtube_open_failed"))

    def open_play_store(self) -> None:
        url = f"https://play.google.com/store/apps/details?id={APP_PACKAGE_NAME}"
        try:
            if platform == "android":
                from jnius import autoclass

                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                market_uri = Uri.parse(f"market://details?id={APP_PACKAGE_NAME}")
                intent = Intent(Intent.ACTION_VIEW, market_uri)
                try:
                    PythonActivity.mActivity.startActivity(intent)
                except Exception:
                    PythonActivity.mActivity.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    )
            else:
                import webbrowser

                webbrowser.open(url)
        except Exception as error:
            log_exception("open_play_store", error)

    def _check_for_update(self) -> None:
        if not self._has_network_connection():
            return

        def worker() -> None:
            ssl_context = None
            if platform == "android":
                # CPython embedded in the APK does not automatically inherit the
                # Android CA store.  Use the device trust store so the update
                # check works on Android 9-15 without disabling TLS validation.
                try:
                    import ssl

                    bundled_ca = (
                        Path(__file__).resolve().parent / "assets" / "cacert.pem"
                    )
                    ssl_context = ssl.create_default_context(
                        cafile=str(bundled_ca) if bundled_ca.exists() else None
                    )
                    for trust_store in (
                        "/system/etc/security/cacerts",
                        "/apex/com.android.conscrypt/cacerts",
                    ):
                        if os.path.isdir(trust_store):
                            ssl_context.load_verify_locations(capath=trust_store)
                except Exception as error:
                    log_exception("update_check_tls", error)
                    ssl_context = None
            last_error: Exception | None = None
            for url in UPDATE_CHECK_URLS:
                try:
                    request = urllib.request.Request(
                        url,
                        headers={"User-Agent": f"BM-Text-to-Voice/{__version__}"},
                    )
                    with urllib.request.urlopen(
                        request,
                        timeout=8,
                        context=ssl_context,
                    ) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    latest_code = int(data.get("version_code") or data.get("versionCode") or 0)
                    if latest_code > APP_VERSION_CODE:
                        Clock.schedule_once(lambda _dt: self._show_update_available())
                    return
                except Exception as error:
                    last_error = error
            if last_error is not None:
                log_event(
                    "update_check_unavailable",
                    error_type=type(last_error).__name__,
                    message=str(last_error),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _show_update_available(self) -> None:
        if self._active_popup is not None:
            Clock.schedule_once(lambda _dt: self._show_update_available(), 2.0)
            return
        self._dialog(
            self.t("update_available"),
            [
                (self.t("later"), lambda: None),
                (self.t("update_now"), self.open_play_store),
            ],
        )

    def _complete_youtube_prompt(self, open_channel: bool = False) -> None:
        self.youtube_prompt_shown = True
        self._save_settings(youtube_prompt_shown=True)
        log_event(
            "youtube_support_prompt_completed",
            action="open_channel" if open_channel else "continue",
        )
        if open_channel:
            self.open_developer_channel()

    def _show_first_launch_youtube_prompt(self, _dt=0) -> None:
        if self.youtube_prompt_shown:
            return
        if self._active_popup is not None:
            Clock.schedule_once(self._show_first_launch_youtube_prompt, 1.5)
            return
        self._dialog(
            self.t("youtube_prompt_message"),
            [
                (
                    self.t("youtube_continue"),
                    lambda: self._complete_youtube_prompt(False),
                ),
                (
                    self.t("youtube_open_channel"),
                    lambda: self._complete_youtube_prompt(True),
                ),
            ],
            title=self.t("youtube_prompt_title"),
        )
        log_event("youtube_support_prompt_shown", language=self.ui_language)

    def _dialog(
        self,
        message: str,
        buttons: list[tuple[str, Callable[[], None]]],
        title: str = "",
    ) -> None:
        content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )
        # The message is scrollable and texture-sized. Fixed character-count
        # estimates overflowed on phones whose Android font scale is larger.
        message_scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
            bar_color=BLUE,
            always_overscroll=False,
        )
        label = make_label(
            message, height=1, font_size="10sp", halign="center"
        )
        label.bind(
            texture_size=lambda widget, value: setattr(
                widget, "height", max(dp(80), value[1] + dp(18))
            )
        )
        message_scroll.bind(
            width=lambda widget, value: setattr(
                label, "text_size", (max(dp(120), value - dp(18)), None)
            )
        )
        message_scroll.add_widget(label)
        content.add_widget(message_scroll)
        stacked_actions = len(buttons) > 1
        actions = BoxLayout(
            orientation="vertical" if stacked_actions else "horizontal",
            size_hint_y=None,
            height=dp(98 if stacked_actions else 48),
            spacing=dp(6 if stacked_actions else 8),
        )
        popup = Popup(
            title=title,
            title_size="12sp",
            content=content,
            size_hint=(0.88, None),
            height=max(dp(300), min(dp(440), Window.height * 0.68)),
            auto_dismiss=False,
            separator_color=BLUE,
        )
        self._active_popup = popup
        Clock.schedule_once(self._sync_admob_banners, 0)

        def popup_dismissed(_popup) -> None:
            if self._active_popup is popup:
                self._active_popup = None
            Clock.schedule_once(self._sync_admob_banners, 0)

        popup.bind(on_dismiss=popup_dismissed)
        for caption, callback in buttons:
            button = StyledButton(
                text=caption,
                font_size="9sp",
                size_hint_y=None,
                height=dp(46),
            )

            def pressed(_button, selected=callback):
                popup.dismiss()
                selected()

            button.bind(on_release=pressed)
            actions.add_widget(button)
        content.add_widget(actions)
        popup.open()

    def _show_error(self, message: str) -> None:
        technical_markers = (
            "Traceback",
            "JVM exception",
            "ClassNotFoundException",
            "NoClassDefFoundError",
            "IncompleteRead",
            "Connection broken",
            "org.",
            "java.",
            "android/",
            "tensor(",
            "CPUExecutionProvider",
        )
        if any(marker.lower() in str(message).lower() for marker in technical_markers):
            message = self.t("technical_error_hidden")
        self._dialog(
            message,
            [(self.t("close"), lambda: None)],
            title=self.t("error"),
        )

    def _show_message(self, message: str) -> None:
        self._dialog(
            message,
            [(self.t("close"), lambda: None)],
            title=self.title,
        )

    def _confirm(self, message: str, callback: Callable[[], None]) -> None:
        self._dialog(
            message,
            [
                (self.t("no"), lambda: None),
                (self.t("yes"), callback),
            ],
        )

    def _offer_resume_session(self, *_args) -> None:
        session = load_generation_session(self.session_dir)
        if not session:
            return
        self._dialog(
            self.t("resume_session"),
            [
                (
                    self.t("no"),
                    lambda: discard_generation_session(self.session_dir),
                ),
                (
                    self.t("yes"),
                    lambda: self._start_generation(
                        resume=True,
                        session_data=session,
                    ),
                ),
            ],
        )

    def on_start(self) -> None:
        self.clone_billing.initialize()
        self.clone_billing_event_version = self.clone_billing.snapshot().event_version
        self.clone_billing_poll = Clock.schedule_interval(
            self._poll_clone_billing, 1.5
        )
        self._refresh_voice_clone_ui()
        self.refresh_voices(force_catalog=False)
        Clock.schedule_once(self._offer_resume_session, 0.8)
        if self._voice_precision_migrated:
            Clock.schedule_once(
                lambda _dt: self._show_message(self.t("fp16_incompatible")),
                2.2,
            )
        if not self.youtube_prompt_shown:
            Clock.schedule_once(self._show_first_launch_youtube_prompt, 12.0)
        Clock.schedule_once(lambda _dt: self._check_for_update(), 18.0)
        if platform == "android":
            try:
                from android.permissions import Permission, request_permissions
                from jnius import autoclass

                BuildVersion = autoclass("android.os.Build$VERSION")
                if int(BuildVersion.SDK_INT) < 29:
                    request_permissions([Permission.WRITE_EXTERNAL_STORAGE])
            except Exception:
                pass
            try:
                self.apply_theme(self.theme)
            except Exception as error:
                log_exception("android_theme_start", error)

    def on_pause(self):
        if self.player.is_playing():
            self.player.pause()
        return True

    def on_stop(self) -> None:
        if self.clone_billing_poll is not None:
            try:
                self.clone_billing_poll.cancel()
            except Exception:
                pass
            self.clone_billing_poll = None
        self.clone_billing.shutdown()
        self.cancel_event.set()
        self.download_cancel_event.set()
        if self.voice_consent_record_purpose:
            if self.voice_consent_record_purpose == "live":
                self.voice_consent_cancel_requested = True
                self.voice_consent.cancel_challenge()
            self._stop_voice_consent_recording()
        if self.voice_consent_record_poll is not None:
            try:
                self.voice_consent_record_poll.cancel()
            except Exception:
                pass
            self.voice_consent_record_poll = None
        self.player.release()
        if self._android_result_poll_event is not None:
            try:
                self._android_result_poll_event.cancel()
            except Exception:
                pass
            self._android_result_poll_event = None


if __name__ == "__main__":
    BMVoiceMobileApp().run()
