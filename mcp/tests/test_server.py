import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cascade_cms.cmstypes import Asset, CascadeError, IdentifierType, ListElements
from cascade_cms_rest_mcp import server
from mcp.server.mcpserver.exceptions import ToolError

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeWrapper:
    """Stands in for CascadeWrapperBase: registers operations (ignored) and
    returns a pre-baked submit_requests() result, mirroring the real
    context-manager shape."""

    def __init__(self, submit_result):
        self.operations = MagicMock()
        self._submit_result = submit_result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def submit_requests(self, *args, **kwargs):
        return self._submit_result


@pytest.fixture
def patch_wrapper(monkeypatch):
    def _patch(submit_result):
        monkeypatch.setattr(server, "_wrapper", lambda: _FakeWrapper(submit_result))

    return _patch


def _identifier() -> IdentifierType:
    return IdentifierType(
        identifier=uuid.uuid4(),
        asset_type="page",
        path={"path": "/a/my-page", "siteName": "example-site"},
    )


def test_cascade_search_returns_formatted_results(patch_wrapper):
    elements = ListElements.model_validate(
        {"matches": [_identifier().model_dump(by_alias=True)]}
    )
    patch_wrapper([elements])

    result = server.cascade_search(query="foo", site="example-site")

    assert result["total_count"] == 1
    assert result["results"][0]["site"] == "example-site"
    assert result["results"][0]["name"] == "my-page"


def test_cascade_search_raises_tool_error_on_cascade_error(patch_wrapper):
    patch_wrapper([CascadeError(success=False, message="Site not found")])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_search(query="foo", site="nope")

    assert "Site not found" in str(exc_info.value)


def test_cascade_search_raises_tool_error_on_empty_submit_result(patch_wrapper):
    patch_wrapper([])

    with pytest.raises(ToolError):
        server.cascade_search(query="foo", site="example-site")


def test_cascade_read_asset_concise_never_returns_uncollapsed_container(patch_wrapper):
    asset = Asset(
        {
            "asset": {
                "page": {
                    "id": "abc123",
                    "name": "My Page",
                    "metadata": {"title": "hi"},
                }
            }
        }
    )
    patch_wrapper([asset])

    result = server.cascade_read_asset(identifier=_identifier())

    assert result["id"] == "abc123"
    assert result["metadata"]["_collapsed"] is True


def test_cascade_read_asset_detailed_returns_raw_payload(patch_wrapper):
    raw = {"id": "abc123", "metadata": {"title": "hi"}}
    asset = Asset({"asset": {"page": raw}})
    patch_wrapper([asset])

    result = server.cascade_read_asset(identifier=_identifier(), format="detailed")

    assert result == raw


def test_cascade_read_asset_raises_tool_error_on_cascade_error(patch_wrapper):
    patch_wrapper([CascadeError(success=False, message="Asset not found")])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_read_asset(identifier=_identifier())

    message = str(exc_info.value)
    assert "Asset not found" in message
    assert "cascade_search" in message


def test_cascade_read_asset_raises_tool_error_on_empty_submit_result(patch_wrapper):
    patch_wrapper([])

    with pytest.raises(ToolError):
        server.cascade_read_asset(identifier=_identifier())


@pytest.mark.parametrize("asset_type", ["user", "group", "role", "message"])
def test_cascade_read_asset_blocks_sensitive_asset_types(patch_wrapper, asset_type):
    patch_wrapper([Asset({"asset": {asset_type: {"id": "abc123", "name": "x"}}})])
    identifier = IdentifierType(identifier=uuid.uuid4(), asset_type=asset_type)

    with pytest.raises(ToolError) as exc_info:
        server.cascade_read_asset(identifier=identifier)

    assert asset_type in str(exc_info.value)


def test_cascade_read_asset_blocks_sensitive_asset_type_before_any_request(monkeypatch):
    """The guard must fire before _wrapper() is ever entered - no network call
    for a blocked type, even a failing one."""

    def _boom():
        raise AssertionError("_wrapper() should not be called for a blocked asset type")

    monkeypatch.setattr(server, "_wrapper", _boom)
    identifier = IdentifierType(identifier=uuid.uuid4(), asset_type="user")

    with pytest.raises(ToolError):
        server.cascade_read_asset(identifier=identifier)


def test_cascade_read_asset_allows_ordinary_asset_type(patch_wrapper):
    asset = Asset({"asset": {"page": {"id": "abc123", "name": "My Page"}}})
    patch_wrapper([asset])

    result = server.cascade_read_asset(identifier=_identifier())

    assert result["id"] == "abc123"


def test_cascade_query_asset_plain_path_detailed(patch_wrapper):
    asset = Asset(
        {
            "asset": {
                "metadataset": {
                    "id": "abc123",
                    "metadata": {"dynamicFields": [{"name": "color", "value": "red"}]},
                }
            }
        }
    )
    patch_wrapper([asset])

    result = server.cascade_query_asset(
        identifier=_identifier(),
        query="metadata.dynamicFields[0].value",
        format="detailed",
    )

    assert result["total_count"] == 1
    assert result["matches"][0]["value"] == "red"
    assert result["matches"][0]["path"] == "$.metadata.dynamicFields[0].value"


def test_cascade_query_asset_concise_collapses_large_nested_match(patch_wrapper):
    asset = Asset(
        {
            "asset": {
                "metadataset": {
                    "id": "abc123",
                    "metadata": {"dynamicFields": [{"name": "color", "value": "red"}]},
                }
            }
        }
    )
    patch_wrapper([asset])

    result = server.cascade_query_asset(identifier=_identifier(), query="metadata")

    match = result["matches"][0]
    assert match["value"]["_collapsed"] is True
    assert match["value"]["expand_with"] == (
        'cascade_query_asset(query="$.metadata", format="detailed")'
    )


def test_cascade_query_asset_wildcard_returns_multiple_matches(patch_wrapper):
    asset = Asset(
        {
            "asset": {
                "metadataset": {
                    "items": [{"name": "a"}, {"name": "b"}],
                }
            }
        }
    )
    patch_wrapper([asset])

    result = server.cascade_query_asset(
        identifier=_identifier(), query='items["*"]', format="detailed"
    )

    assert result["total_count"] == 2
    assert [m["value"] for m in result["matches"]] == [{"name": "a"}, {"name": "b"}]


def test_cascade_query_asset_find_matches_by_key_regardless_of_nesting(patch_wrapper):
    asset = Asset(
        {
            "asset": {
                "metadataset": {
                    "identifier": "top",
                    "group": {"identifier": "nested"},
                }
            }
        }
    )
    patch_wrapper([asset])

    result = server.cascade_query_asset(
        identifier=_identifier(), query='find("identifier")', format="detailed"
    )

    assert result["total_count"] == 2
    assert {m["value"] for m in result["matches"]} == {"top", "nested"}


def test_cascade_query_asset_no_matches_returns_empty_not_an_error(patch_wrapper):
    asset = Asset({"asset": {"metadataset": {"id": "abc123"}}})
    patch_wrapper([asset])

    result = server.cascade_query_asset(
        identifier=_identifier(), query="does.missing"
    )

    assert result["matches"] == []
    assert result["total_count"] == 0


def test_cascade_query_asset_invalid_query_raises_tool_error(patch_wrapper):
    asset = Asset({"asset": {"metadataset": {"id": "abc123"}}})
    patch_wrapper([asset])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_query_asset(identifier=_identifier(), query="a + b")

    message = str(exc_info.value)
    assert "a + b" in message


@pytest.mark.parametrize("asset_type", ["user", "group", "role", "message"])
def test_cascade_query_asset_blocks_sensitive_asset_types(patch_wrapper, asset_type):
    patch_wrapper([Asset({"asset": {asset_type: {"id": "abc123", "name": "x"}}})])
    identifier = IdentifierType(identifier=uuid.uuid4(), asset_type=asset_type)

    with pytest.raises(ToolError) as exc_info:
        server.cascade_query_asset(identifier=identifier, query="id")

    assert asset_type in str(exc_info.value)


def _load_asset(name: str) -> Asset:
    with open(FIXTURES / name) as f:
        return Asset(json.load(f))


@pytest.fixture
def content_type() -> Asset:
    return _load_asset("contentType_resp.json")


@pytest.fixture
def data_definition() -> Asset:
    return _load_asset("raw_data_def.json")


@pytest.fixture
def page(content_type) -> Asset:
    return Asset({"asset": {"page": {"contentTypeId": content_type.get("id")}}})


def test_cascade_get_data_structure_lists_children(
    patch_wrapper_sequence, page, content_type, data_definition
):
    patch_wrapper_sequence([page, content_type, data_definition])

    result = server.cascade_get_data_structure(
        identifier=_identifier(), group="right-column"
    )

    assert result["group"] == "right-column"
    assert result["data_definition"]["id"] == data_definition.get("id")
    assert [c["identifier"] for c in result["children"]] == ["display", "widget"]
    assert result["total_count"] == 2
    assert result["has_more"] is False
    assert "expand_with" not in result


def test_cascade_get_data_structure_returns_one_node(
    patch_wrapper_sequence, page, content_type, data_definition
):
    patch_wrapper_sequence([page, content_type, data_definition])

    result = server.cascade_get_data_structure(
        identifier=_identifier(), group="right-column", node_identifier="widget"
    )

    assert result["node"]["tag"] == "asset"
    assert result["node"]["attributes"]["identifier"] == "widget"


def test_cascade_get_data_structure_direct_data_definition_id_short_circuits(
    patch_wrapper_sequence, data_definition
):
    block = Asset({"asset": {"block": {"dataDefinitionId": data_definition.get("id")}}})
    patch_wrapper_sequence([block, data_definition])

    result = server.cascade_get_data_structure(
        identifier=_identifier(), group="right-column"
    )

    assert result["group"] == "right-column"


def test_cascade_get_data_structure_group_not_found(
    patch_wrapper_sequence, page, content_type, data_definition
):
    patch_wrapper_sequence([page, content_type, data_definition])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_get_data_structure(identifier=_identifier(), group="nope")

    message = str(exc_info.value)
    assert "nope" in message
    assert "right-column" in message  # a real group name, present in the listing


def test_cascade_get_data_structure_node_not_found(
    patch_wrapper_sequence, page, content_type, data_definition
):
    patch_wrapper_sequence([page, content_type, data_definition])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_get_data_structure(
            identifier=_identifier(), group="right-column", node_identifier="nope"
        )

    message = str(exc_info.value)
    assert "nope" in message
    assert "widget" in message


def test_cascade_get_data_structure_truncates_with_limit_and_expand_hint(
    patch_wrapper_sequence, page, content_type, data_definition
):
    patch_wrapper_sequence([page, content_type, data_definition])

    result = server.cascade_get_data_structure(
        identifier=_identifier(), group="right-column", limit=1
    )

    assert len(result["children"]) == 1
    assert result["has_more"] is True
    assert result["expand_with"].startswith("cascade_read_asset(")
    assert data_definition.get("id") in result["expand_with"]


def test_cascade_get_data_structure_no_resolvable_reference(patch_wrapper_sequence):
    orphan = Asset({"asset": {"file": {"name": "x"}}})
    patch_wrapper_sequence([orphan])

    with pytest.raises(ToolError, match="contentTypeId"):
        server.cascade_get_data_structure(identifier=_identifier(), group="anything")


def test_cascade_get_page_config_lists_configurations(
    patch_wrapper_sequence, page, content_type
):
    patch_wrapper_sequence([page, content_type])

    result = server.cascade_get_page_config(identifier=_identifier())

    assert result["content_type"]["name"] == "Standard Page"
    names = [c["name"] for c in result["configurations"]]
    assert names == ["ASPX", "XML"]
    assert result["total_count"] == 2
    assert result["has_more"] is False


def test_cascade_get_page_config_config_name_not_found(
    patch_wrapper_sequence, page, content_type
):
    patch_wrapper_sequence([page, content_type])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_get_page_config(
            identifier=_identifier(), configuration_name="nope"
        )

    message = str(exc_info.value)
    assert "nope" in message
    assert "ASPX" in message


def test_cascade_get_page_config_region_names_come_from_instance_not_content_type(
    patch_wrapper_sequence, content_type
):
    page_with_config = Asset(
        {
            "asset": {
                "page": {
                    "contentTypeId": content_type.get("id"),
                    "pageConfigurations": [
                        {
                            "name": "ASPX",
                            "pageRegions": [{"name": "DEFAULT", "content": "hi"}],
                        }
                    ],
                }
            }
        }
    )
    patch_wrapper_sequence([page_with_config, content_type])

    result = server.cascade_get_page_config(
        identifier=_identifier(), configuration_name="ASPX"
    )

    assert result["region_names_on_this_instance"] == ["DEFAULT"]


def test_cascade_get_page_config_page_region_without_configuration_name_raises(
    patch_wrapper_sequence,
):
    with pytest.raises(ToolError, match="configuration_name"):
        server.cascade_get_page_config(identifier=_identifier(), page_region="DEFAULT")


def test_cascade_get_page_config_page_region_returns_content(
    patch_wrapper_sequence, content_type
):
    page_with_config = Asset(
        {
            "asset": {
                "page": {
                    "contentTypeId": content_type.get("id"),
                    "pageConfigurations": [
                        {
                            "name": "ASPX",
                            "pageRegions": [{"name": "DEFAULT", "content": "hello"}],
                        }
                    ],
                }
            }
        }
    )
    patch_wrapper_sequence([page_with_config, content_type])

    result = server.cascade_get_page_config(
        identifier=_identifier(), configuration_name="ASPX", page_region="DEFAULT"
    )

    assert result["region"]["content"] == "hello"


def test_cascade_get_page_config_page_region_not_authored_on_instance(
    patch_wrapper_sequence, content_type
):
    page_with_config = Asset(
        {
            "asset": {
                "page": {
                    "contentTypeId": content_type.get("id"),
                    "pageConfigurations": [{"name": "ASPX", "pageRegions": []}],
                }
            }
        }
    )
    patch_wrapper_sequence([page_with_config, content_type])

    with pytest.raises(ToolError, match="never authored"):
        server.cascade_get_page_config(
            identifier=_identifier(), configuration_name="ASPX", page_region="FOOTER"
        )


def _site_asset(**overrides) -> Asset:
    data = {
        "id": uuid.uuid4().hex,
        "name": "example-site",
        "rootDataDefinitionContainerId": uuid.uuid4().hex,
        "rootSharedFieldContainerId": uuid.uuid4().hex,
        "rootFolderId": uuid.uuid4().hex,
    }
    data.update(overrides)
    return Asset({"asset": {"site": data}})


def test_cascade_root_container_id_returns_hex_id(patch_wrapper):
    site = _site_asset()
    patch_wrapper([site])

    result = server.cascade_root_container_id(
        site_identifier=_identifier(), asset_type="folder"
    )

    assert result == {"container_id": site.get("rootFolderId")}


def test_cascade_root_container_id_not_a_site_raises(patch_wrapper):
    page = Asset({"asset": {"page": {"id": uuid.uuid4().hex, "name": "not-a-site"}}})
    patch_wrapper([page])

    with pytest.raises(ToolError, match="expected a site asset"):
        server.cascade_root_container_id(
            site_identifier=_identifier(), asset_type="folder"
        )


def test_cascade_root_container_id_unmapped_type_raises(patch_wrapper):
    site = _site_asset()
    del site._data["rootFolderId"]
    patch_wrapper([site])

    with pytest.raises(ToolError, match="folder"):
        server.cascade_root_container_id(
            site_identifier=_identifier(), asset_type="folder"
        )


def test_cascade_root_container_id_raises_tool_error_on_cascade_error(patch_wrapper):
    patch_wrapper([CascadeError(success=False, message="Site not found")])

    with pytest.raises(ToolError, match="Site not found"):
        server.cascade_root_container_id(
            site_identifier=_identifier(), asset_type="folder"
        )


def test_cascade_list_sites_returns_formatted_sites(patch_wrapper):
    elements = ListElements.model_validate(
        {
            "sites": [
                IdentifierType(
                    identifier=uuid.uuid4(), asset_type="site", path={"path": ""}
                ).model_dump(by_alias=True)
            ]
        }
    )
    patch_wrapper([elements])

    result = server.cascade_list_sites()

    assert result["total_count"] == 1
    assert result["has_more"] is False
    assert result["sites"][0]["type"] == "site"


def test_cascade_list_sites_truncates_with_limit(patch_wrapper):
    raw = [
        IdentifierType(
            identifier=uuid.uuid4(), asset_type="site", path={"path": ""}
        ).model_dump(by_alias=True)
        for _ in range(5)
    ]
    elements = ListElements.model_validate({"sites": raw})
    patch_wrapper([elements])

    result = server.cascade_list_sites(limit=2)

    assert result["total_count"] == 5
    assert result["has_more"] is True
    assert len(result["sites"]) == 2


def test_cascade_list_sites_raises_tool_error_on_cascade_error(patch_wrapper):
    patch_wrapper([CascadeError(success=False, message="listSites unavailable")])

    with pytest.raises(ToolError, match="listSites unavailable"):
        server.cascade_list_sites()


def test_wrapper_disables_exit_on_failure(monkeypatch):
    captured = {}

    class _Spy:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("CASCADE_API_KEY", "k")
    monkeypatch.setenv("CASCADE_URL", "https://example.test")
    monkeypatch.setattr(server, "CascadeWrapperBase", _Spy)

    server._wrapper()

    assert captured["exit_on_failure"] is False


def test_wrapper_missing_credentials_is_tool_error_not_system_exit(monkeypatch):
    monkeypatch.delenv("CASCADE_API_KEY", raising=False)
    monkeypatch.delenv("CASCADE_URL", raising=False)

    with pytest.raises(ToolError, match="CASCADE_API_KEY"):
        server._wrapper()


def test_batch_error_becomes_tool_error(monkeypatch):
    from cascade_cms.failures import CascadeBatchError

    class _Broken(_FakeWrapper):
        def submit_requests(self, *args, **kwargs):
            try:
                raise ConnectionError("refused")
            except ConnectionError as cause:
                raise CascadeBatchError("batch broke") from cause

    monkeypatch.setattr(server, "_wrapper", lambda: _Broken([]))

    with pytest.raises(ToolError, match="ConnectionError: refused"):
        server.cascade_search(query="foo", site="example-site")


def test_failed_read_with_real_wrapper_is_tool_error(monkeypatch):
    """Acceptance #10: real CascadeWrapperBase (stub driver) with
    exit_on_failure=False turns a CascadeError read into a ToolError; no
    SystemExit escapes.

    Copied from py-cascade-cms tests/test_wrapper.py (StubDriver and
    make_wrapper). make_wrapper bypasses __init__ and sets three private
    attributes: _callback_failures, _has_reportable_failure and
    _exit_on_failure. If the library renames one, this test breaks here
    first - re-sync it from that file.
    """
    import asyncio

    from cascade_cms import OperationLogger
    from cascade_cms.operations import Operations
    from cascade_cms.wrapper import CascadeWrapperBase

    class StubDriver:
        base_url = "https://example.test/api/v1"

        def __init__(self, responses):
            self.responses = list(responses)
            self.eventLoop = asyncio.new_event_loop()

        def _build_url(self, *segments):
            return "/".join([self.base_url, *map(str, segments)])

        async def execute_requests(self, requests):
            return self.responses.pop(0)

        def close(self):
            self.eventLoop.close()

    def make_wrapper():
        driver = StubDriver(
            [[CascadeError(success=False, message="not found")]]
        )
        wrapper = object.__new__(CascadeWrapperBase)
        wrapper._driver = driver
        wrapper._logger = MagicMock(spec=OperationLogger)
        wrapper.operations = Operations(driver, _logger=wrapper._logger)
        wrapper._callback_failures = []
        wrapper._has_reportable_failure = False
        wrapper._exit_on_failure = False
        return wrapper

    monkeypatch.setattr(server, "_wrapper", make_wrapper)

    with pytest.raises(ToolError, match="not found"):
        server.cascade_read_asset(identifier=_identifier())


def test_mcp_source_only_queues_read_operations():
    """Read-only guard: every `.operations.<name>` in the MCP package
    must be a read operation. A new write operation fails this test."""
    import ast

    read_only = {"read", "search", "listSites"}
    used: set[str] = set()
    for path in Path(server.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "operations"
            ):
                used.add(node.attr)

    assert used, "guard found no operations - is it still scanning?"
    assert used <= read_only, f"non-read operations: {used - read_only}"


def test_cascade_search_rejects_blocked_asset_type_before_request(
    patch_wrapper,
):
    patch_wrapper([])

    with pytest.raises(ToolError) as exc_info:
        server.cascade_search(query="x", site="s", asset_types=["user"])

    assert "not accessible" in str(exc_info.value)


def test_cascade_search_filters_blocked_results(patch_wrapper):
    blocked = {
        "id": str(uuid.uuid4()),
        "type": "user",
        "path": {"path": "/u", "siteName": "s"},
    }
    ok = _identifier().model_dump(by_alias=True)
    patch_wrapper([ListElements.model_validate({"matches": [blocked, ok]})])

    result = server.cascade_search(query="x", site="s")

    assert result["total_count"] == 1
    assert result["filtered_count"] == 1


@pytest.mark.parametrize(
    "limit,expected", [(0, 1), (-1, 1), (None, 5), (500, 5)]
)
def test_list_sites_limit_clamping(patch_wrapper, limit, expected):
    raw = [_identifier().model_dump(by_alias=True) for _ in range(5)]
    patch_wrapper([ListElements.model_validate({"matches": raw})])

    result = server.cascade_list_sites(limit=limit)

    assert len(result["sites"]) == expected


def test_wrapper_passes_log_dir_and_creates_no_local_logs(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CASCADE_API_KEY", "k")
    monkeypatch.setenv("CASCADE_URL", "https://x")
    monkeypatch.setenv("CASCADE_MCP_LOG_DIR", str(tmp_path / "logs-elsewhere"))
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(server, "CascadeWrapperBase", fake)

    server._wrapper()

    assert captured["log_dir"] == tmp_path / "logs-elsewhere"
    assert captured["exit_on_failure"] is False
    assert not (tmp_path / "logs").exists()
