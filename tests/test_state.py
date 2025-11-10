from statemachine import State


class SubclassedState(State):
    pass


class StateWithName(State, name="foo"):
    pass


def test_name():
    assert State().name.startswith("S")
    assert State("A").name == "A"
    assert State("a").name == "a"
    assert SubclassedState().name == SubclassedState.__name__
    assert StateWithName().name == "foo"


def test_calling_handlers():
    s = State()
    s.is_applicable(None)
    s.on_entry(None)
    s.on_exit(None)
