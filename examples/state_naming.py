from statemachine import StateMachine, State, FinalState


class StateB(State):
    """Subclassed state.

    Name of the subclass is used as a name by default.
    """


class StateC(State, name="C"):
    """Subclassed state with a class-level name attribute.

    Name is be given as a class-level class attribute.
    """


class Machine(StateMachine):

    def __init__(self):
        super().__init__()
        self.a = State()       # "State 1"
        self.b = StateB()      # "StateB"
        self.c = StateC()      # "C"
        self.d = FinalState()  # "FinalState"

        self._from_a_to_b = self.connect(self.a, self.b, name="ab")  # manual
        self.connect(self.b, self.c, automatic=True, name="bc")      # automatic
        self.connect(self.c, self.d, automatic=True, name="cd")      # automatic

        self.initial_state = self.a

    def from_a_to_b(self):
        self._from_a_to_b.trigger()

    def on_state_changed(self, from_state: State, to_state: State):
        """Log state transitions."""
        print(f"State changed: {from_state} → {to_state}.")


sm = Machine()
sm.start()
sm.from_a_to_b()
sm.join()
