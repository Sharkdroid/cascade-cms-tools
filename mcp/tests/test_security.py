from cascade_cms_rest_mcp import security


def test_blocked_types_are_not_allowed():
    for asset_type in security.BLOCKED_ASSET_TYPES:
        assert security.is_asset_type_blocked(asset_type)
        assert not security.is_asset_type_allowed(asset_type)


def test_allowed_and_blocked_sets_are_disjoint():
    assert not set(security.ALLOWED_ASSET_TYPES) & set(security.BLOCKED_ASSET_TYPES)


def test_ordinary_asset_type_is_allowed_and_not_blocked():
    assert security.is_asset_type_allowed("page")
    assert not security.is_asset_type_blocked("page")


def test_case_insensitive():
    assert security.is_asset_type_blocked("User")
    assert security.is_asset_type_allowed("Page")


def test_unknown_asset_type_is_neither_allowed_nor_blocked():
    """Fail-closed for a type not in either static list (a typo, or a future
    library release adding a genuinely new asset type)."""
    assert not security.is_asset_type_allowed("not-a-real-type")
    assert not security.is_asset_type_blocked("not-a-real-type")
