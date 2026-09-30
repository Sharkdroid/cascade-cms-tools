import json

import pytest
from cascade_cms_rest_mcp.query import QueryError, evaluate, parse_query


def _matches(data, query_text):
    return evaluate(data, parse_query(query_text))


def test_plain_dotted_path_returns_one_match():
    data = {"metadata": {"title": "hi"}}

    matches = _matches(data, "metadata.title")

    assert len(matches) == 1
    assert matches[0].value == "hi"
    assert matches[0].path == "$.metadata.title"


def test_bracket_string_key_equivalent_to_dotted():
    data = {"metadata": {"title": "hi"}}

    dotted = _matches(data, "metadata.title")
    bracketed = _matches(data, 'metadata["title"]')

    assert dotted == bracketed


def test_integer_and_negative_index():
    data = {"items": ["a", "b", "c"]}

    assert _matches(data, "items[0]")[0].value == "a"
    assert _matches(data, "items[-1]")[0].value == "c"
    assert _matches(data, "items[0]")[0].path == "$.items[0]"
    assert _matches(data, "items[-1]")[0].path == "$.items[-1]"


def test_wildcard_over_a_list():
    data = {"items": [{"name": "a"}, {"name": "b"}]}

    matches = _matches(data, 'items["*"]')

    assert [m.value for m in matches] == [{"name": "a"}, {"name": "b"}]
    assert [m.path for m in matches] == ["$.items[0]", "$.items[1]"]


def test_wildcard_over_a_dict():
    data = {"metadata": {"title": "hi", "author": "bob"}}

    matches = _matches(data, 'metadata["*"]')

    values = {m.path: m.value for m in matches}
    assert values == {"$.metadata.title": "hi", "$.metadata.author": "bob"}


def test_find_matches_at_multiple_depths_including_nested_under_itself():
    data = {
        "identifier": "top",
        "group": {
            "identifier": "mid",
            "child": {"identifier": "bottom"},
        },
    }

    matches = _matches(data, 'find("identifier")')

    values = {m.path: m.value for m in matches}
    assert values == {
        "$.identifier": "top",
        "$.group.identifier": "mid",
        "$.group.child.identifier": "bottom",
    }


def test_find_chained_after_a_path_scopes_the_search():
    data = {
        "identifier": "top-level, not in scope",
        "metadata": {"nested": {"identifier": "in scope"}},
    }

    matches = _matches(data, 'metadata.find("identifier")')

    assert len(matches) == 1
    assert matches[0].value == "in scope"


def test_missing_path_returns_no_matches_not_an_error():
    data = {"metadata": {"title": "hi"}}

    assert _matches(data, "metadata.missing") == []
    assert _matches(data, "missing.title") == []


def test_empty_query_returns_the_whole_root():
    data = {"metadata": {"title": "hi"}}

    matches = _matches(data, "")

    assert len(matches) == 1
    assert matches[0].value == data
    assert matches[0].path == "$"


@pytest.mark.parametrize(
    "bad_query",
    [
        "__import__('os')",
        "a + b",
        "a if b else c",
        "lambda: 1",
        "a.b()",
        "a[b]",
        "a['x'] = 1",
    ],
)
def test_rejected_syntax_raises_query_error_before_touching_data(bad_query):
    with pytest.raises(QueryError):
        parse_query(bad_query)


_SAMPLE = {
    "title": "t",
    "metadata": {
        "title": "m",
        "dynamicFields": [{"name": "a"}, {"name": "b", "title": "x"}],
    },
    "x": [1, 2],
}


def test_dollar_alone_equals_empty_query():
    assert _matches(_SAMPLE, "$") == _matches(_SAMPLE, "")
    assert _matches(_SAMPLE, " $ ") == _matches(_SAMPLE, "")


def test_returned_paths_round_trip_as_queries():
    for key in ("title", "name", "dynamicFields"):
        for found in _matches(_SAMPLE, f'find("{key}")'):
            again = _matches(_SAMPLE, found.path)
            assert again == [found]


def test_expand_with_hint_query_parses():
    import re

    from cascade_cms_rest_mcp.formatting import _collapse_query_match

    match = _matches(_SAMPLE, "metadata.dynamicFields")[0]
    hint = _collapse_query_match(match.path, match.value)["expand_with"]
    query_text = re.search(r'query="([^"]*)"', hint).group(1)

    assert _matches(_SAMPLE, query_text) == [match]


def test_expand_with_hint_escapes_quoted_key_paths():
    import re

    from cascade_cms_rest_mcp.formatting import _collapse_query_match

    data = {"metadata": {"odd key": {"a": 1}}}
    match = _matches(data, 'metadata["odd key"]')[0]
    hint = _collapse_query_match(match.path, match.value)["expand_with"]
    raw = re.search(r'query=("(?:[^"\\]|\\.)*")', hint).group(1)

    assert json.loads(raw) == match.path
    assert _matches(data, json.loads(raw)) == [match]


def test_plain_forms_still_work():
    assert _matches(_SAMPLE, "metadata")[0].path == "$.metadata"
    name = "metadata.dynamicFields[0].name"
    assert _matches(_SAMPLE, name)[0].value == "a"
    assert len(_matches(_SAMPLE, 'find("title")')) == 3
    assert len(_matches(_SAMPLE, 'metadata.find("title")')) == 2
    assert len(_matches(_SAMPLE, 'x["*"]')) == 2


@pytest.mark.parametrize(
    "bad",
    ["metadata.$x", "$$.metadata", "$.", '$["metadata"]', "$metadata"],
)
def test_misplaced_dollar_is_rejected(bad):
    with pytest.raises(QueryError):
        parse_query(bad)


def test_dynamic_fields_example_parses_and_returns_value():
    data = {
        "metadata": {
            "dynamicFields": [
                {"name": "audience", "fieldValues": [{"value": "v"}]}
            ]
        }
    }
    q = "metadata.dynamicFields[0].fieldValues[0].value"

    assert _matches(data, q)[0].value == "v"
    # the old, wrong example (no such key) matches nothing
    assert _matches(data, "metadata.dynamicFields[0].value") == []


def test_non_identifier_keys_get_bracket_paths():
    data = {"m": {"odd key": 1, "a.b": 2, "class": 3, "plain": 4}}

    paths = {x.path for x in _matches(data, 'm["*"]')}

    assert paths == {
        '$.m["odd key"]',
        '$.m["a.b"]',
        '$.m["class"]',
        "$.m.plain",
    }


def test_non_identifier_key_paths_round_trip():
    data = {"m": {"odd key": {"x": 1}, "a.b": {"x": 2}, "q\"t": 5}}
    for key in ("odd key", "a.b", 'q"t', "x"):
        for found in _matches(data, f"find({json.dumps(key)})"):
            assert _matches(data, found.path) == [found]


def test_literal_bracket_key_is_not_an_index():
    data = {"m": {"[0]": "k"}, "n": ["i"]}

    assert _matches(data, "m.find(\"[0]\")")[0].path == '$.m["[0]"]'
    assert _matches(data, "n[0]")[0].path == "$.n[0]"
