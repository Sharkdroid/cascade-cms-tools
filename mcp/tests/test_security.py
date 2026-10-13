import pytest
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


@pytest.mark.parametrize("asset_type", security.ALLOWED_ASSET_TYPES)
def test_every_allowed_type_passes_in_listed_and_lower_case(asset_type):
    assert security.is_asset_type_allowed(asset_type)
    assert security.is_asset_type_allowed(asset_type.lower())


@pytest.mark.parametrize("asset_type", security.BLOCKED_ASSET_TYPES)
def test_every_blocked_type_is_blocked_in_any_case(asset_type):
    for variant in (asset_type, asset_type.upper(), asset_type.title()):
        assert security.is_asset_type_blocked(variant)
        assert not security.is_asset_type_allowed(variant)


@pytest.mark.parametrize(
    "variant",
    ["users", "Users", " user ", "groups", "roles", "messages", "audit",
     "audits", "activity", "activities", "ACTIVITY"],
)
def test_aliases_of_blocked_types_are_blocked(variant):
    assert security.is_asset_type_blocked(variant)
    assert not security.is_asset_type_allowed(variant)


def test_mask_identity_fields_is_nested_case_insensitive_and_pure():
    raw = {
        "createdBy": "a",
        "CREATEDBY2": "keep",
        "metadata": {"author": "b", "tags": [{"Owner": "c", "x": 1}]},
        "n": 3,
    }

    masked = security.mask_identity_fields(raw)

    assert masked == {
        "createdBy": "[REDACTED]",
        "CREATEDBY2": "keep",
        "metadata": {
            "author": "[REDACTED]",
            "tags": [{"Owner": "[REDACTED]", "x": 1}],
        },
        "n": 3,
    }
    assert raw["createdBy"] == "a"


def test_is_guarded_reference():
    assert security.is_guarded_reference({"type": "user", "name": "x"})
    assert security.is_guarded_reference({"type": "Groups"})
    assert not security.is_guarded_reference({"type": "page"})
    assert not security.is_guarded_reference({"name": "x"})
    assert not security.is_guarded_reference("user")


@pytest.mark.parametrize(
    "term", ["createdBy", "LastModifiedBy", "lastPublishedBy", " users ", "audit", "role"]
)
def test_guarded_terms(term):
    assert security.is_guarded_term(term)


def test_ordinary_search_terms_are_not_guarded():
    assert not security.is_guarded_term("annual report")
    assert not security.is_guarded_term("who created this page")


def test_mask_group_and_user_name_lists():
    raw = {
        "roleAssignments": [
            {"roleId": "8", "roleName": "Admin", "groups": "A;B", "users": "u1"}
        ],
        "applicableGroupNames": "PIO Approvers;PIO Contributors",
    }

    masked = security.mask_identity_fields(raw)

    assert masked["roleAssignments"][0] == {
        "roleId": "8",
        "roleName": "Admin",
        "groups": "[REDACTED]",
        "users": "[REDACTED]",
    }
    assert masked["applicableGroupNames"] == "[REDACTED]"
