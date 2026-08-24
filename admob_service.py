"""AdMob configuration and safe Python wrapper for the Android Java bridge."""

from __future__ import annotations

from kivy.utils import platform

from app_log import log_event, log_exception


ADMOB_APP_ID = "ca-app-pub-2408723079137167~4524564324"
ADMOB_APP_OPEN_ID = "ca-app-pub-2408723079137167/3211628443"
ADMOB_INTERSTITIAL_ID = "ca-app-pub-2408723079137167/4236558209"
ADMOB_BANNER_UNITS = {
    "top": "ca-app-pub-2408723079137167/3211482655",
    "middle": "ca-app-pub-2408723079137167/8767207456",
    "bottom": "ca-app-pub-2408723079137167/8878742300",
}
ADMOB_SDK_VERSION = "25.4.0"


class AdMobBannerManager:
    """Thin wrapper around ``org.bmtts.bmtextspeech.BmAdMobBridge``.

    The Java bridge owns native AdMob callbacks. This keeps the Kivy/PyJNIus
    side small and makes desktop/unsupported-device fallback harmless.
    """

    def __init__(self) -> None:
        self.enabled = platform == "android"
        self.initialized = False
        self.failed = False
        self.activity = None

    def start(self) -> None:
        if not self.enabled or self.failed:
            return
        try:
            from jnius import autoclass, cast

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            current = PythonActivity.mActivity
            if current is None:
                raise RuntimeError("Android activity is unavailable")
            # mActivity is declared as the Kivy base class.  Cast it to the
            # real subclass so modal/permission bridge methods remain visible
            # through PyJNIus on physical devices.
            self.activity = cast("org.bmtts.bmtextspeech.BmPythonActivity", current)
            self.activity.initializeAds(ADMOB_INTERSTITIAL_ID)
            self.initialized = True
            log_event("admob_bridge_initialized", app_id=ADMOB_APP_ID)
        except Exception as error:  # pragma: no cover - Android runtime only
            self.failed = True
            log_exception("admob_bridge_start_failed", error)

    def show_app_open(self) -> None:
        if not self.initialized or self.failed:
            return
        try:
            self.activity.loadAndShowAppOpenAd(ADMOB_APP_OPEN_ID)
            log_event(
                "admob_app_open_show_requested",
                unit_id=ADMOB_APP_OPEN_ID,
            )
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception("admob_app_open_show_failed", error)

    def preload_app_open(self) -> None:
        if not self.initialized or self.failed:
            return
        try:
            self.activity.loadAppOpenAd(ADMOB_APP_OPEN_ID)
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception("admob_app_open_preload_failed", error)

    def preload_interstitial(self) -> None:
        if not self.initialized or self.failed:
            return
        try:
            self.activity.loadInterstitialAd(ADMOB_INTERSTITIAL_ID)
            log_event(
                "admob_interstitial_preload_requested",
                unit_id=ADMOB_INTERSTITIAL_ID,
            )
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception("admob_interstitial_preload_failed", error)

    def show_interstitial(self) -> None:
        if not self.initialized or self.failed:
            return
        try:
            self.activity.showInterstitialAd(ADMOB_INTERSTITIAL_ID)
            log_event(
                "admob_interstitial_show_requested",
                unit_id=ADMOB_INTERSTITIAL_ID,
            )
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception("admob_interstitial_show_failed", error)

    def load_banner(self, slot: str) -> None:
        if not self.initialized or self.failed:
            return
        unit_id = ADMOB_BANNER_UNITS.get(slot)
        if not unit_id:
            return
        try:
            self.activity.loadBanner(slot, unit_id)
            log_event("admob_banner_requested", slot=slot, unit_id=unit_id)
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception(f"admob_banner_request_failed_{slot}", error)

    def update_banner_frame(
        self,
        slot: str,
        x: float,
        y: float,
        width: float,
        height: float,
        window_height: float,
        visible: bool,
    ) -> None:
        if not self.initialized or self.failed:
            return
        try:
            self.activity.updateBannerFrame(
                slot,
                int(x),
                int(y),
                int(width),
                int(height),
                int(window_height),
                bool(visible),
            )
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception(f"admob_banner_position_failed_{slot}", error)

    def suspend_banners(self, suspended: bool) -> None:
        """Hide native banners while a Kivy modal is above the SDL canvas."""
        if not self.initialized or self.failed or self.activity is None:
            return
        try:
            self.activity.setNativeBannersSuspended(bool(suspended))
        except Exception as error:  # pragma: no cover - Android runtime only
            log_exception("admob_banner_suspend_failed", error)
