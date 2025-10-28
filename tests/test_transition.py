from statemachine import State
from statemachine import StateMachine


class MyStateMachine(StateMachine):
    def __init__(self):
        super().__init__()
        self.a = State()
        self.b = State()
        self.c = State()

        self.ab = self.connect(self.a, self.b, name="a → b")
        self.bc = self.connect(self.b, self.c, automatic=True)
        self.reset = self.connect_any(self.a)

        self.initial_state = self.a


def test_can_transition():
    sm = MyStateMachine()

    assert sm.ab.can_transition_from(sm.a) == True
    assert sm.ab.can_transition_from(sm.b) == False
    assert sm.ab.can_transition_from(sm.c) == False

    assert sm.reset.can_transition_from(sm.a) == True
    assert sm.reset.can_transition_from(sm.b) == True
    assert sm.reset.can_transition_from(sm.c) == True


def test_name():
    sm = MyStateMachine()

    assert sm.ab.name == "a → b"
    assert sm.bc.name.startswith("T")


def test_is_applicable():
    sm = MyStateMachine()
    assert sm.ab.is_applicable(context=None)


def test_usage():
    sm = MyStateMachine()

    assert sm.a in sm.ab.from_states
    assert sm.b is sm.ab.to_state
    assert sm.ab.automatic == False
    assert sm.bc.automatic == True


def test_callback():
    class Machine(StateMachine):
        def __init__(self):
            super().__init__()
            self.a = State()
            self.b = State()
            self.ab = self.connect(self.a, self.b, callback=self._set_value)
            self.initial_state = self.a
            self.callback_value = False

        def _set_value(self, context):
            self.callback_value = True

    sm = Machine()
    sm.start()
    assert sm.callback_value == False
    sm.ab()
    assert sm.callback_value == True
