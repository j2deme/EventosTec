from app.utils.slug_utils import slugify, generate_unique_slug


class DummyModel:
    public_slug = None


class DummySession:
    def __init__(self, existing):
        self._existing = existing

    def query(self, col):
        class Q:
            def __init__(self, items):
                self._items = items

            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return [(i,) for i in self._items]

        return Q(self._existing)


def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("Árbol ñandú") == "arbol-nandu"
    assert slugify("   Multiple   spaces   ") == "multiple-spaces"


def test_generate_unique_slug_no_conflict():
    s = DummySession([])
    slug = generate_unique_slug(s, DummyModel, "My Activity")
    assert slug == "my-activity"


def test_generate_unique_slug_with_conflicts():
    s = DummySession(["my-activity", "my-activity-1", "my-activity-2"])
    slug = generate_unique_slug(s, DummyModel, "My Activity")
    assert slug == "my-activity-3"
