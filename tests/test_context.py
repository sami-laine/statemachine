from dataclasses import dataclass

from statemachine import StateMachine, State, FinalState, T


@dataclass
class Context:
    value: int = 0


class StateWithContext(State[Context]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_applicable_value = -1
        self.on_entry_value = -1
        self.on_exit_value = -1

    def is_applicable(self, context: Context) -> bool:
        self.is_applicable_value = context.value
        return True

    def on_entry(self, context: Context):
        self.on_entry_value = context.value

    def on_exit(self, context: Context):
        self.on_exit_value = context.value


def test_setting_context():
    context = Context()
    sm = StateMachine(context)
    assert sm.context is context


def test_state_hooks():
    value = 42
    context = Context(value=value)

    sm = StateMachine(context)
    a = StateWithContext("A")
    b = StateWithContext("B")
    sm.connect(a, b, automatic=True)
    sm.connect(b, FinalState(), automatic=True)

    sm.initial_state = a
    sm.start()
    sm.join()

    # is applicable is not called for the initial state.
    assert a.on_entry_value == value
    assert a.on_exit_value == value

    assert b.is_applicable_value == value
    assert b.on_entry_value == value
    assert b.on_exit_value == value



