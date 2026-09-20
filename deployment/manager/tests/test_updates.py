from weave_cbt_manager.core.updates import is_newer, version_tuple


def test_semver_comparison():
    assert version_tuple("v1.2.3") == (1, 2, 3)
    assert is_newer("1.3.0", "1.2.9") is True
    assert is_newer("1.2.0", "1.2.0") is False
