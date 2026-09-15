from tools.governance import change_guard as cg


def test_change_guard_empty_mapping_string_walk() -> None:
    assert list(cg.iter_strings({})) == []
    assert list(cg.iter_strings(42)) == []
