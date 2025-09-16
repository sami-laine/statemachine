from statemachine import FinalState
from statemachine import State
from statemachine import StateMachine
from statemachine.diagram import show_state_diagram


class ExampleMachine(StateMachine):
    """Example state machine."""

    def __init__(self):
        super().__init__()

        a = State()
        b = State()
        c = State()
        f = FinalState()

        self.connect(a, b, automatic=True)
        self.connect(a, c, name="ac", automatic=True)
        self.connect(b, f, name="bf")
        self.connect(c, f, name="cf")

        self.initial_state = a


sm = ExampleMachine()

# Shows state machine state diagram on default web browser.
show_state_diagram(sm)
