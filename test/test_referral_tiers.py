"""What a referrer earns, by who they brought in.

The prototype prices these differently: a therapist bringing another
therapist is worth more to the platform than a patient bringing a friend,
so one flat number would either overpay or underpay somebody.
"""
from types import SimpleNamespace

from app.services.points import DEFAULT_CONFIG, _referral_amount


def user(role):
    return SimpleNamespace(role=role)


class TestTiers:
    def test_a_patient_referring_a_friend_earns_the_friend_rate(self):
        assert _referral_amount(DEFAULT_CONFIG, user("PATIENT"), user("PATIENT")) == 500

    def test_a_therapist_bringing_a_therapist_earns_the_higher_tier(self):
        assert _referral_amount(DEFAULT_CONFIG, user("THERAPIST"), user("THERAPIST")) == 1000

    def test_a_therapist_bringing_a_patient_earns_the_patient_tier(self):
        assert _referral_amount(DEFAULT_CONFIG, user("THERAPIST"), user("PATIENT")) == 500

    def test_an_unknown_referrer_still_pays_rather_than_silently_dropping(self):
        # A role added later must not mean the referrer earns nothing.
        assert _referral_amount(DEFAULT_CONFIG, user("ADMIN"), user("PATIENT")) == 500
        assert _referral_amount(DEFAULT_CONFIG, None, user("PATIENT")) == 500

    def test_tiers_follow_config_rather_than_being_hardcoded(self):
        config = {**DEFAULT_CONFIG, "referralAwardTherapistRefersTherapist": 2500}
        assert _referral_amount(config, user("THERAPIST"), user("THERAPIST")) == 2500


class TestOneSided:
    def test_the_referee_is_not_paid_for_being_invited(self):
        # The design shows a single figure, the referrer's.
        assert DEFAULT_CONFIG["referralAwardsBothSides"] is False
