import uuid

import pytest
from cascade_cms.cmstypes import CascadeError, IdentifierType, Path
from cascade_cms_rest_mcp.errors import (
    describe_identifier,
    read_asset_error,
    search_failure_error,
    single_result,
    unexpected_failure_error,
)
from mcp.server.mcpserver.exceptions import ToolError


def test_single_result_empty_list_raises_tool_error():
    with pytest.raises(ToolError) as exc_info:
        single_result([], context="cascade_search")

    message = str(exc_info.value)
    assert "cascade_search" in message
    assert "CASCADE_URL" in message
    assert "CASCADE_API_KEY" in message


def test_single_result_returns_first_element():
    sentinel = object()

    assert single_result([sentinel], context="cascade_search") is sentinel


def test_describe_identifier_for_identifier_type():
    identifier = IdentifierType(identifier=uuid.uuid4(), asset_type="page")

    described = describe_identifier(identifier)

    assert described.startswith("page ")


def test_describe_identifier_for_path():
    path = Path(path="/a/b", site_name="my-site", asset_type="page")

    described = describe_identifier(path)

    assert described == "page at my-site:/a/b"


def test_search_failure_error_uses_cascade_error_message():
    error = CascadeError(success=False, message="Site 'nope' not found")

    tool_error = search_failure_error(error)

    assert "Site 'nope' not found" in str(tool_error)
    assert "cascade_search" in str(tool_error)


def test_search_failure_error_falls_back_on_empty_message():
    error = CascadeError(success=False, message="")

    tool_error = search_failure_error(error)

    assert str(tool_error)  # never an empty/bare message


def test_search_failure_error_for_arbitrary_exception_gives_connectivity_hint():
    tool_error = search_failure_error(RuntimeError("boom"))

    message = str(tool_error)
    assert "CASCADE_URL" in message
    assert "CASCADE_API_KEY" in message


def test_read_asset_error_mentions_identifier_and_suggests_search():
    identifier = IdentifierType(identifier=uuid.uuid4(), asset_type="page")
    error = CascadeError(success=False, message="Asset not found")

    tool_error = read_asset_error(identifier, error)

    message = str(tool_error)
    assert "Asset not found" in message
    assert "cascade_search" in message
    assert "page" in message


def test_unexpected_failure_error_includes_tool_name():
    tool_error = unexpected_failure_error("cascade_read_asset", RuntimeError("boom"))

    message = str(tool_error)
    assert "cascade_read_asset" in message
    assert "boom" in message


def test_unexpected_failure_error_maps_batch_error_with_cause():
    from cascade_cms.failures import CascadeBatchError

    try:
        try:
            raise ConnectionError("refused")
        except ConnectionError as cause:
            raise CascadeBatchError("batch broke") from cause
    except CascadeBatchError as batch:
        tool_error = unexpected_failure_error("cascade_search", batch)

    message = str(tool_error)
    assert "cascade_search" in message
    assert "ConnectionError: refused" in message
    assert "CASCADE_URL" in message


def test_single_result_accepts_chain_results():
    from cascade_cms.failures import ChainResults

    assert single_result(ChainResults(["x"]), context="c") == "x"


def test_tool_errors_mask_the_api_token(monkeypatch):
    token = "sekrit-token-abcd"
    monkeypatch.setenv("CASCADE_API_KEY", token)

    error = unexpected_failure_error(
        "cascade_search", RuntimeError(f"bad Bearer {token}")
    )

    assert token not in str(error)
    assert "****abcd" in str(error)


def test_batch_failure_masks_the_api_token(monkeypatch):
    from cascade_cms.failures import CascadeBatchError

    token = "sekrit-token-wxyz"
    monkeypatch.setenv("CASCADE_API_KEY", token)
    try:
        try:
            raise ConnectionError(f"with {token}")
        except ConnectionError as cause:
            raise CascadeBatchError("x") from cause
    except CascadeBatchError as batch:
        error = unexpected_failure_error("t", batch)

    assert token not in str(error)
    assert "****wxyz" in str(error)
