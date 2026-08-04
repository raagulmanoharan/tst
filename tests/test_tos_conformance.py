"""The Google data boundary.

If any of these fail, the system is storing Google Maps Content, which Maps
Platform ToS 3.2.3(a)(iii) prohibits and which risks immediate suspension under
5.2(d). Do not relax these tests to make a feature work — the feature is wrong.

See CLAUDE.md rule 3.
"""

from __future__ import annotations

import pytest

from leadgen.discover.places import EphemeralPlace
from leadgen.store.models import (
    FORBIDDEN_PERSISTED_FIELDS,
    Lead,
    PersistedModel,
    TosViolation,
)


def _all_persisted_models() -> list[type[PersistedModel]]:
    seen: list[type[PersistedModel]] = []

    def walk(cls: type[PersistedModel]) -> None:
        for sub in cls.__subclasses__():
            seen.append(sub)
            walk(sub)

    walk(PersistedModel)
    return seen


def test_no_persisted_model_stores_google_content():
    import leadgen.pipeline  # noqa: F401  — ensure every model module is imported

    offenders = {
        cls.__name__: sorted(set(cls.model_fields) & FORBIDDEN_PERSISTED_FIELDS)
        for cls in _all_persisted_models()
        if set(cls.model_fields) & FORBIDDEN_PERSISTED_FIELDS
    }
    assert not offenders, f"models persisting Google Maps Content: {offenders}"


@pytest.mark.parametrize(
    "field_name,annotation",
    [
        ("rating", float),
        ("user_rating_count", int),
        ("business_name", str),
        ("formatted_address", str),
        ("phone", str),
        ("website_uri", str),
        ("reviews", list),
    ],
)
def test_guard_rejects_google_fields_at_definition(field_name, annotation):
    with pytest.raises(TosViolation):
        type("Offender", (PersistedModel,), {"__annotations__": {field_name: annotation}})


def test_guard_allows_derived_observations():
    """Facts *about* a site are ours; the site's Google listing is not."""
    model = type(
        "Derived",
        (PersistedModel,),
        {"__annotations__": {"load_seconds": float, "copyright_year": int, "mobile_viewport": bool}},
    )
    assert set(model.model_fields) == {"load_seconds", "copyright_year", "mobile_viewport"}


def test_ephemeral_place_is_outside_the_persisted_tree():
    """`EphemeralPlace` holds Google fields, so it must never be persistable."""
    assert not issubclass(EphemeralPlace, PersistedModel)
    assert not hasattr(EphemeralPlace, "model_dump")


def test_lead_stores_only_place_id_and_geo_from_google():
    google_derived = {"place_id", "lat", "lng", "geo_observed_at"}
    assert google_derived <= set(Lead.model_fields)
    assert not set(Lead.model_fields) & FORBIDDEN_PERSISTED_FIELDS
