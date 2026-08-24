from __future__ import annotations

import json

from voice_clone_billing import (
    FREE_COMPLETED_GENERATIONS,
    VOICE_CLONE_LIFETIME_PRODUCT_ID,
    VoiceCloneBilling,
    billing_text,
)


def test_exactly_ten_completed_generations_are_free(tmp_path):
    billing = VoiceCloneBilling(tmp_path, platform_name="desktop")
    for completed in range(1, FREE_COMPLETED_GENERATIONS + 1):
        assert billing.can_start_generation()
        state = billing.record_completed_generation()
        assert state.completed_generations == completed

    assert not billing.can_start_generation()
    state = billing.record_completed_generation()
    assert state.completed_generations == FREE_COMPLETED_GENERATIONS
    assert state.remaining_free == 0


def test_quota_survives_service_recreation(tmp_path):
    first = VoiceCloneBilling(tmp_path, platform_name="desktop")
    first.record_completed_generation()
    first.record_completed_generation()
    second = VoiceCloneBilling(tmp_path, platform_name="desktop")
    assert second.snapshot().completed_generations == 2
    assert second.snapshot().remaining_free == 8


def test_corrupt_counter_fails_safely_without_crashing(tmp_path):
    (tmp_path / "voice_clone_quota.json").write_text("not-json", encoding="utf-8")
    billing = VoiceCloneBilling(tmp_path, platform_name="desktop")
    assert billing.snapshot().completed_generations == 0
    assert billing.can_start_generation()


class _OwnedBridge:
    @staticmethod
    def initialize(activity, product_id, free_limit):
        assert product_id == VOICE_CLONE_LIFETIME_PRODUCT_ID
        assert free_limit == FREE_COMPLETED_GENERATIONS

    @staticmethod
    def getStateJson(activity):
        return json.dumps({"productId": VOICE_CLONE_LIFETIME_PRODUCT_ID,"billingAvailable": True,"connected": True,"productAvailable": True,"lifetimeOwned": True,"purchasePending": False,"freeLimit": 10,"completedGenerations": 10,"localizedPrice": "500 ₸","currencyCode": "KZT","priceMicros": 500_000_000,"priceConfigurationOk": True,"status": "owned"})

    @staticmethod
    def recordCompletedGeneration(activity):
        raise AssertionError("paid generations must not consume the free quota")


def test_owned_non_consumable_unlocks_after_free_quota(tmp_path):
    billing = VoiceCloneBilling(tmp_path, bridge=_OwnedBridge, activity=object(), platform_name="android")
    state = billing.initialize()
    assert state.lifetime_owned
    assert state.can_generate
    assert state.localized_price == "500 ₸"
    assert billing.record_completed_generation().lifetime_owned


def test_ui_copy_is_localized_and_uses_store_price(tmp_path):
    billing = VoiceCloneBilling(tmp_path, bridge=_OwnedBridge, activity=object(), platform_name="android")
    for language in ("kk", "ru", "en"):
        ui = billing.ui_state(language)
        assert ui["purchase_button_text"]
        assert "500" in ui["purchase_button_text"]
    assert "500" not in billing_text("en", "buy_price_loading")
