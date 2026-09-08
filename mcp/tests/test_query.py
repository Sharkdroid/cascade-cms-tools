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
