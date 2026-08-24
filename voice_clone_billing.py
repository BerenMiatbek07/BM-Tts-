"""Google Play lifetime entitlement and the free voice-clone quota.

The Android billing bridge is asynchronous.  This module exposes a small,
pollable API for Kivy and keeps a second app-private quota record so a missing
or temporarily unavailable Java bridge never turns the paid feature into an
unlimited free feature.

Only call :meth:`record_completed_generation` after the final cloned audio
file has been created and validated.  Starting, cancelling, or failing a job
must not consume a free generation.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


VOICE_CLONE_LIFETIME_PRODUCT_ID = "voice_clone_lifetime"
FREE_COMPLETED_GENERATIONS = 10
PLAY_BILLING_LIBRARY_VERSION = "9.1.0"


BILLING_TEXT = {
    "kk": {
        "title": "Дауыс клондау — өмірлік қолжетімділік",
        "free_remaining": "Тегін мүмкіндік: {remaining}/{limit}",
        "quota_exhausted": "10 тегін дыбыстама қолданылды. Жалғастыру үшін өмірлік қолжетімділікті сатып алыңыз.",
        "buy": "Өмірлік ашу · {price}",
        "buy_price_loading": "Google Play бағасын жүктеу…",
        "restore": "Сатып алуды қалпына келтіру",
        "owned": "Өмірлік қолжетімділік ашық",
        "pending": "Төлем өңделіп жатыр. Расталғаннан кейін мүмкіндік автоматты түрде ашылады.",
        "purchase_cancelled": "Сатып алу аяқталмады.",
        "billing_unavailable": "Google Play төлемі қазір қолжетімсіз. Интернетті және Play Store аккаунтын тексеріңіз.",
        "product_unavailable": "Өнім Google Play Console ішінде әлі жарияланбаған немесе бұл аккаунтқа қолжетімсіз.",
        "price_configuration_error": "Қазақстан бағасы Google Play Console ішінде дәл 500 ₸ болып орнатылуы керек.",
        "purchase_error": "Сатып алуды бастау мүмкін болмады. Қайталап көріңіз.",
    },
    "ru": {
        "title": "Клонирование голоса — пожизненный доступ",
        "free_remaining": "Бесплатно осталось: {remaining}/{limit}",
        "quota_exhausted": "10 бесплатных озвучек использованы. Для продолжения купите пожизненный доступ.",
        "buy": "Открыть навсегда · {price}",
        "buy_price_loading": "Загрузка цены Google Play…",
        "restore": "Восстановить покупку",
        "owned": "Пожизненный доступ открыт",
        "pending": "Платёж обрабатывается. Доступ откроется автоматически после подтверждения.",
        "purchase_cancelled": "Покупка не завершена.",
        "billing_unavailable": "Оплата Google Play сейчас недоступна. Проверьте интернет и аккаунт Play Store.",
        "product_unavailable": "Товар ещё не опубликован в Google Play Console или недоступен этому аккаунту.",
        "price_configuration_error": "Цена для Казахстана должна быть установлена в Google Play Console ровно на 500 ₸.",
        "purchase_error": "Не удалось начать покупку. Попробуйте ещё раз.",
    },
    "en": {
        "title": "Voice cloning — lifetime access",
        "free_remaining": "Free generations left: {remaining}/{limit}",
        "quota_exhausted": "All 10 free generations have been used. Buy lifetime access to continue.",
        "buy": "Unlock forever · {price}",
        "buy_price_loading": "Loading the Google Play price…",
        "restore": "Restore purchase",
        "owned": "Lifetime access is unlocked",
        "pending": "Your payment is pending. Access will unlock automatically after confirmation.",
        "purchase_cancelled": "The purchase was not completed.",
        "billing_unavailable": "Google Play billing is unavailable. Check your connection and Play Store account.",
        "product_unavailable": "The product is not published in Google Play Console yet or is unavailable to this account.",
        "price_configuration_error": "The Kazakhstan price must be configured in Google Play Console as exactly 500 ₸.",
        "purchase_error": "Could not start the purchase. Please try again.",
    },
}


def billing_text(language: str, key: str, **values: Any) -> str:
    """Return billing UI text without exposing raw BillingClient errors."""

    code = (language or "en").lower().split("-", 1)[0]
    table = BILLING_TEXT.get(code, BILLING_TEXT["en"])
    template = table.get(key, BILLING_TEXT["en"].get(key, key))
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


@dataclass(frozen=True)
class BillingSnapshot:
    product_id: str = VOICE_CLONE_LIFETIME_PRODUCT_ID
    billing_available: bool = False
    connected: bool = False
    product_available: bool = False
    lifetime_owned: bool = False
    purchase_pending: bool = False
    free_limit: int = FREE_COMPLETED_GENERATIONS
    completed_generations: int = 0
    remaining_free: int = FREE_COMPLETED_GENERATIONS
    can_generate: bool = True
    localized_price: str = ""
    currency_code: str = ""
    price_micros: int = 0
    price_configuration_ok: bool = True
    status: str = "idle"
    response_code: int = 0
    event_version: int = 0
    last_verified_at_ms: int = 0
    verification_mode: str = "play_client_only"

    @classmethod
    def from_bridge_json(cls, raw: str | None) -> "BillingSnapshot":
        try:
            data = json.loads(raw or "{}")
        except (TypeError, ValueError):
            data = {}

        def number(name: str, default: int = 0) -> int:
            try:
                return int(data.get(name, default))
            except (TypeError, ValueError):
                return default

        limit = max(0, number("freeLimit", FREE_COMPLETED_GENERATIONS))
        completed = max(0, number("completedGenerations", 0))
        owned = bool(data.get("lifetimeOwned", False))
        return cls(
            product_id=str(data.get("productId") or VOICE_CLONE_LIFETIME_PRODUCT_ID),
            billing_available=bool(data.get("billingAvailable", False)),
            connected=bool(data.get("connected", False)),
            product_available=bool(data.get("productAvailable", False)),
            lifetime_owned=owned,
            purchase_pending=bool(data.get("purchasePending", False)),
            free_limit=limit,
            completed_generations=completed,
            remaining_free=max(0, limit - completed),
            can_generate=owned or completed < limit,
            localized_price=str(data.get("localizedPrice") or ""),
            currency_code=str(data.get("currencyCode") or ""),
            price_micros=max(0, number("priceMicros", 0)),
            price_configuration_ok=bool(data.get("priceConfigurationOk", True)),
            status=str(data.get("status") or "idle"),
            response_code=number("responseCode", 0),
            event_version=number("eventVersion", 0),
            last_verified_at_ms=max(0, number("lastVerifiedAtMs", 0)),
            verification_mode=str(data.get("verificationMode") or "play_client_only"),
        )


class _QuotaStore:
    """Small atomic app-private counter used as a fail-closed mirror."""

    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path else None
        self._memory_completed = 0
        self._lock = threading.RLock()

    def completed(self) -> int:
        with self._lock:
            if self.path is None:
                return self._memory_completed
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return max(0, int(data.get("completed_generations", 0)))
            except (OSError, TypeError, ValueError):
                return self._memory_completed

    def set_at_least(self, value: int) -> int:
        with self._lock:
            value = max(self.completed(), max(0, int(value)))
            self._memory_completed = value
            if self.path is not None:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                    temporary.write_text(
                        json.dumps(
                            {"completed_generations": value},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        encoding="utf-8",
                    )
                    temporary.replace(self.path)
                except OSError:
                    pass
            return value

    def increment(self, limit: int) -> int:
        with self._lock:
            current = self.completed()
            return self.set_at_least(min(max(0, int(limit)), current + 1))


class VoiceCloneBilling:
    """Pollable billing/quota facade used by the Kivy UI and generation code."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        *,
        bridge: Any | None = None,
        activity: Any | None = None,
        platform_name: str | None = None,
        personal_unlimited: bool = False,
    ) -> None:
        quota_path = Path(data_dir) / "voice_clone_quota.json" if data_dir else None
        self._quota = _QuotaStore(quota_path)
        self._bridge = bridge
        self._activity = activity
        self._bridge_failed = False
        self.personal_unlimited = bool(personal_unlimited)
        if platform_name is None:
            try:
                from kivy.utils import platform as kivy_platform

                platform_name = kivy_platform
            except Exception:
                platform_name = "desktop"
        self.platform_name = platform_name

    def _ensure_android_bridge(self) -> bool:
        if self._bridge_failed:
            return False
        if self.platform_name != "android":
            return self._bridge is not None
        if self._bridge is not None and self._activity is not None:
            return True
        try:
            from jnius import autoclass
            from android_activity import get_bm_activity
            self._bridge = autoclass("org.bmtts.bmtextspeech.BmBillingBridge")
            self._activity = get_bm_activity()
            return True
        except Exception:
            self._bridge_failed = True
            self._bridge = None
            return False

    def initialize(self) -> BillingSnapshot:
        if self._ensure_android_bridge():
            try:
                self._bridge.initialize(
                    self._activity,
                    VOICE_CLONE_LIFETIME_PRODUCT_ID,
                    FREE_COMPLETED_GENERATIONS,
                )
            except Exception:
                self._bridge_failed = True
                self._bridge = None
        return self.snapshot()

    def snapshot(self) -> BillingSnapshot:
        if self.personal_unlimited and self.platform_name != "android":
            return BillingSnapshot(
                lifetime_owned=True,
                remaining_free=FREE_COMPLETED_GENERATIONS,
                can_generate=True,
                status="personal_unlimited",
                verification_mode="personal_noncommercial",
            )
        bridge_state: BillingSnapshot | None = None
        if self._ensure_android_bridge():
            try:
                bridge_state = BillingSnapshot.from_bridge_json(
                    str(self._bridge.getStateJson(self._activity))
                )
            except Exception:
                self._bridge_failed = True
                self._bridge = None

        local_completed = self._quota.completed()
        if bridge_state is None:
            completed = min(FREE_COMPLETED_GENERATIONS, local_completed)
            return BillingSnapshot(
                completed_generations=completed,
                remaining_free=max(0, FREE_COMPLETED_GENERATIONS - completed),
                can_generate=completed < FREE_COMPLETED_GENERATIONS,
                status="billing_unavailable" if self.platform_name == "android" else "local_only",
            )

        completed = max(local_completed, bridge_state.completed_generations)
        self._quota.set_at_least(completed)
        completed = min(bridge_state.free_limit, completed)
        return replace(
            bridge_state,
            completed_generations=completed,
            remaining_free=max(0, bridge_state.free_limit - completed),
            can_generate=bridge_state.lifetime_owned or completed < bridge_state.free_limit,
        )

    def can_start_generation(self) -> bool:
        return self.snapshot().can_generate

    def record_completed_generation(self) -> BillingSnapshot:
        before = self.snapshot()
        if before.lifetime_owned or self.personal_unlimited:
            return before
        java_completed: int | None = None
        if self._ensure_android_bridge():
            try:
                java_completed = int(
                    self._bridge.recordCompletedGeneration(self._activity)
                )
            except Exception:
                self._bridge_failed = True
                self._bridge = None
        if java_completed is None:
            self._quota.increment(before.free_limit)
        else:
            self._quota.set_at_least(java_completed)
        return self.snapshot()

    def launch_purchase(self) -> bool:
        state = self.snapshot()
        if state.lifetime_owned:
            return True
        if not state.price_configuration_ok or not self._ensure_android_bridge():
            return False
        try:
            return bool(self._bridge.launchPurchase(self._activity))
        except Exception:
            self._bridge_failed = True
            self._bridge = None
            return False

    def restore_purchase(self) -> bool:
        if not self._ensure_android_bridge():
            return False
        try:
            self._bridge.refreshPurchases(self._activity)
            return True
        except Exception:
            self._bridge_failed = True
            self._bridge = None
            return False

    def shutdown(self) -> None:
        if not self._ensure_android_bridge():
            return
        try:
            self._bridge.endConnection()
        except Exception:
            pass

    def ui_state(self, language: str) -> dict[str, Any]:
        state = self.snapshot()
        if state.lifetime_owned:
            message_key = "owned"
        elif state.purchase_pending:
            message_key = "pending"
        elif state.status == "price_configuration_error" or not state.price_configuration_ok:
            message_key = "price_configuration_error"
        elif state.can_generate:
            message_key = "free_remaining"
        elif state.status == "product_unavailable":
            message_key = "product_unavailable"
        elif state.status == "purchase_cancelled":
            message_key = "purchase_cancelled"
        elif state.status == "purchase_error":
            message_key = "purchase_error"
        elif not state.billing_available and self.platform_name == "android":
            message_key = "billing_unavailable"
        else:
            message_key = "quota_exhausted"
        price_key = "buy" if state.localized_price else "buy_price_loading"
        return {
            **asdict(state),
            "title_text": billing_text(language, "title"),
            "message_text": billing_text(
                language,
                message_key,
                remaining=state.remaining_free,
                limit=state.free_limit,
            ),
            "quota_text": billing_text(
                language,
                "free_remaining",
                remaining=state.remaining_free,
                limit=state.free_limit,
            ),
            "purchase_button_text": billing_text(
                language,
                price_key,
                price=state.localized_price,
            ),
            "restore_button_text": billing_text(language, "restore"),
            "purchase_enabled": (
                not state.lifetime_owned
                and not state.purchase_pending
                and state.product_available
                and state.price_configuration_ok
            ),
        }


__all__ = [
    "BILLING_TEXT",
    "BillingSnapshot",
    "FREE_COMPLETED_GENERATIONS",
    "PLAY_BILLING_LIBRARY_VERSION",
    "VOICE_CLONE_LIFETIME_PRODUCT_ID",
    "VoiceCloneBilling",
    "billing_text",
]
