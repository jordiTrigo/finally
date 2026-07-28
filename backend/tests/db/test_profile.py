from app.db import get_cash_balance, get_profile, set_cash_balance


def test_get_profile_returns_seeded_row(db):
    profile = get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"]


def test_get_profile_returns_none_for_unknown_user(db):
    assert get_profile(user_id="nobody") is None


def test_set_cash_balance_persists(db):
    set_cash_balance(1234.56)
    assert get_cash_balance() == 1234.56
