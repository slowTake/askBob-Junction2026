import pytest

from app.budget import Plan, plan_for


def test_small_drawing_is_enlarged_and_gets_the_detailed_path() -> None:
    # 1000 x 800 crop at the sheet scale 1.5 is 1500 x 1200 = 1.8 Mpx: under both limits.
    plan = plan_for(1000, 800, desired=1.5, budget_px=16e6, detailed_px=4e6)
    assert plan == Plan(scale=1.5, detailed=True)


def test_mid_size_drawing_keeps_its_scale_but_uses_labels_only() -> None:
    # 2000 x 1500 at 1.5 = 3000 x 2250 = 6.75 Mpx: under the budget, over the detailed limit.
    plan = plan_for(2000, 1500, desired=1.5, budget_px=16e6, detailed_px=4e6)
    assert plan == Plan(scale=1.5, detailed=False)


def test_huge_sheet_is_shrunk_to_the_budget_never_enlarged() -> None:
    # 7536 x 4898 = 36.9 Mpx; sqrt(16e6 / 36.9e6) = 0.658 (by hand); 1.5x would be 83 Mpx.
    plan = plan_for(7536, 4898, desired=1.5, budget_px=16e6, detailed_px=4e6)
    assert plan is not None
    assert plan.scale == pytest.approx(0.6585, abs=1e-3)
    assert plan.detailed is False


def test_too_dense_to_read_is_skipped() -> None:
    # sqrt(16e6 / 400e6) = 0.2, below the 0.35 floor: walls would vanish, so skip.
    assert plan_for(20000, 20000, desired=1.0, budget_px=16e6, detailed_px=4e6) is None


def test_empty_crop_is_skipped() -> None:
    assert plan_for(0, 100, desired=1.0, budget_px=16e6, detailed_px=4e6) is None
