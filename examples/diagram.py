from statemachine import FinalState
from statemachine import State
from statemachine import StateMachine
from statemachine.diagram import show_state_diagram


class ExampleMachine(StateMachine):
    """Example state machine."""

    def __init__(self):
        super().__init__()

        a = State("A")
        b = State("B")
        c = State("C")
        f = FinalState()

        self.connect(self.initial_state, a, automatic=True)
        self.ab = self.connect(a, b)  # Not named
        self.ac = self.connect(a, c, name="ab")
        self.connect(b, f, name="bf", automatic=True)
        self.connect(c, f, name="cf", automatic=True)


sm = ExampleMachine()

# Shows state machine state diagram on default web browser.
show_state_diagram(sm)
