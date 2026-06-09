import hashlib

from prices.enrich.versioning import (
    PROMPT_BYTES_HASH,
    PROMPT_SEMVER,
    SCHEMA_VERSION,
    _sha12,
    cache_key,
    canonical_json,
    input_hash,
)


def test_sha12_truncates_to_12_chars():
    assert len(_sha12(b"hello")) == 12


def test_canonical_json_sorts_keys():
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b == '{"a":2,"b":1}'


def test_canonical_json_handles_nested_dicts():
    a = canonical_json({"a": {"z": 1, "y": 2}, "b": 3})
    b = canonical_json({"b": 3, "a": {"y": 2, "z": 1}})
    assert a == b == '{"a":{"y":2,"z":1},"b":3}'


def test_canonical_json_ensure_ascii_false():
    # Non-ASCII characters must be preserved verbatim, not escaped.
    out = canonical_json({"name": "café"})
    assert "café" in out


def test_input_hash_stable():
    d = {
        "product_name_original": "Coke 1L",
        "category": "Drinks",
        "country": "PH",
        "currency": "PHP",
    }
    h1 = input_hash(d)
    h2 = input_hash(dict(reversed(list(d.items()))))
    assert h1 == h2
    assert len(h1) == 64


def test_cache_key_changes_with_semver(monkeypatch):
    d = {"x": 1}
    k1 = cache_key(d)
    import prices.enrich.versioning as v

    monkeypatch.setattr(v, "PROMPT_SEMVER", "v999")
    expected = hashlib.sha256(
        (canonical_json(d) + "v999" + v.SCHEMA_VERSION + v.TAXONOMY_VERSION).encode()
    ).hexdigest()
    assert v.cache_key(d) == expected
    assert v.cache_key(d) != k1


def test_cache_key_ignores_bytes_hash(monkeypatch):
    """Editing the prompt file must NOT invalidate the cache automatically.

    Only an explicit PROMPT_SEMVER bump should change cache_key. This is the
    whole point of the decoupling — typo fixes shouldn't trigger 41k re-enrich.
    """
    d = {"x": 1}
    k1 = cache_key(d)
    import prices.enrich.versioning as v

    monkeypatch.setattr(v, "PROMPT_BYTES_HASH", "deadbeefdead")
    assert v.cache_key(d) == k1


def test_prompt_semver_and_hashes_well_formed():
    assert PROMPT_SEMVER.startswith("v") and len(PROMPT_SEMVER) >= 2
    assert len(PROMPT_BYTES_HASH) == 12
    assert len(SCHEMA_VERSION) == 12
