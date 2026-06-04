import pytest
from app.agents.scale_guard import snap_scale, _interpolate_gap_years, _corrections_log


def test_snap_leaves_inballpark_values_untouched():
    assert snap_scale(100.0, 110.0) == 100.0          # ratio 0.91 — fine
    assert snap_scale(200.0, 100.0) == 200.0          # ratio 2.0 — within window


def test_snap_fixes_10x_slip():
    _corrections_log.clear()
    # extracted in millions (10x crores)
    assert snap_scale(34830.0, 3483.0, "T", 2023, "revenue_cr") == pytest.approx(3483.0)
    assert _corrections_log[-1]["factor"] == "x10^-1"


def test_snap_nulls_unfixable_actual():
    # standalone vs consolidated AND wrong scale — no power of 10 lands
    assert snap_scale(10996.0, 491246.0, null_if_unfixable=True) is None


def test_snap_keeps_unfixable_forecast():
    # forecasts are never nulled — wild forecast is a finding
    assert snap_scale(10996.0, 491246.0, null_if_unfixable=False) == 10996.0


def test_snap_handles_none_and_zero():
    assert snap_scale(None, 100.0) is None
    assert snap_scale(100.0, None) == 100.0
    assert snap_scale(0.0, 100.0) == 0.0


def test_interpolation_fills_gap_years():
    ref = {2021: {"revenue_cr": 2614.0}, 2024: {"revenue_cr": 4965.0}}
    _interpolate_gap_years(ref)
    assert 2022 in ref and 2023 in ref
    # log-linear: monotonic between endpoints
    assert 2614.0 < ref[2022]["revenue_cr"] < ref[2023]["revenue_cr"] < 4965.0
