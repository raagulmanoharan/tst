from __future__ import annotations

import pytest

from fiftyk.goal import DemandMechanism
from fiftyk.models import Economics, Opportunity
from fiftyk.provenance import Confidence, Observation, SampleBasis, Source
from fiftyk.store import Store


def fig(value: float, basis: SampleBasis = SampleBasis.MEDIAN) -> Observation[float]:
    return Observation[float](
        value=float(value),
        source=Source.INDUSTRY_REPORT,
        method="test fixture figure",
        confidence=Confidence.VERIFIED,
        basis=basis,
        evidence_url="https://fixture.test",
    )


def gap(note: str = "not established in fixtures") -> Observation[float]:
    return Observation[float].unverified(Source.INDUSTRY_REPORT, "test fixture gap", note=note)


def economics(**overrides) -> Economics:
    """A fully-known, deliberately benign set of economics.

    Defaults: ₹250 net per sale, 2 sales per listing per month, 10 hours to
    build one, no decay. At 25 h/week that reaches ₹50,000/mo in ~10 months.
    """
    base = dict(
        capital_required_inr=0.0,
        median_seller_net_monthly_inr=20_000.0,
        net_per_unit_inr=250.0,
        units_per_listing_per_month=2.0,
        build_hours_per_listing=10.0,
        months_to_first_revenue=1.0,
        annual_decay=0.0,
        fixed_upkeep_hours_per_week=0.0,
    )
    base.update(overrides)
    return Economics(
        unit_name="sale",
        listing_name="asset",
        **{k: (gap() if v is None else fig(v)) for k, v in base.items()},
    )


def opportunity(
    key: str = "test_opp",
    mechanism: DemandMechanism = DemandMechanism.MARKETPLACE_SEARCH,
    **econ,
) -> Opportunity:
    return Opportunity(
        key=key,
        name=f"Test {key}",
        category="test",
        summary="fixture",
        demand_mechanism=mechanism,
        economics=economics(**econ),
    )


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()
