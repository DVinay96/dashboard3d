import pytest

from app.policy import PolicyError, clean_statements, is_allowed, is_allowed_any


def st(effect, actions, resources=("*",)):
    return {"effect": effect, "actions": list(actions), "resources": list(resources)}


def test_implicit_deny():
    assert not is_allowed([], "products:read", "project/a/product/1")


def test_wildcards_and_explicit_deny_wins():
    sts = [st("allow", ["*"]), st("deny", ["products:delete"])]
    assert is_allowed(sts, "products:read", "project/a/product/1")
    assert not is_allowed(sts, "products:delete", "project/a/product/1")


def test_resource_scoping():
    sts = [st("allow", ["products:*"], ["project/a/*"])]
    assert is_allowed(sts, "products:read", "project/a/product/1")
    assert not is_allowed(sts, "products:read", "project/b/product/1")


def test_multi_project_any_allow_but_any_deny_wins():
    sts = [st("allow", ["products:read"], ["project/a/*"])]
    assert is_allowed_any(sts, "products:read", ["project/a/product/1", "project/b/product/1"])
    assert not is_allowed_any(sts, "products:read", ["project/b/product/1"])
    sts.append(st("deny", ["products:read"], ["project/b/*"]))
    assert not is_allowed_any(sts, "products:read", ["project/a/product/1", "project/b/product/1"])


@pytest.mark.parametrize("bad", [
    [], [st("permit", ["*"])], [st("allow", ["product:read"])], [st("allow", [])], [st("allow", ["a b"])],
])
def test_clean_statements_rejects(bad):
    with pytest.raises(PolicyError):
        clean_statements(bad)


def test_clean_statements_defaults_resources():
    assert clean_statements([{"effect": "allow", "actions": "products:read"}])[0]["resources"] == ["*"]
