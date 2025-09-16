from dataclasses import dataclass

from statemachine import StateMachine, State, FinalState


@dataclass
class MyContext:
    """Context object passed to each state during transitions."""
    processing_time: float = 1.0


class StateA(State[MyContext]):
    """Custom state with overridden entry behavior."""

    def on_entry(self, context: MyContext):
        """Executed when entering state A."""
        print(f"Context: {context}")


class MyStateMachine(StateMachine[MyContext]):
    """An example state machine with manual and automatic transitions.

    States are defined as instances of State`class. The states are connected by using
    connect() method. This creates and returns a state transition object that can be used
    to trigger the state transition.

    The state transitions can be either manually triggered or automatically executed by
    the state machine.

    To implement custom behavior for a state, subclass `State` and override one or more of
    the following methods:
        - `is_applicable(context)`-> bool
        - `on_entry(context) -> None`
        - `on_exit(context) -> None`

    Each method receives a `context` object, which can represent external data, a device,
    or any other runtime information needed by the state logic.

    This example demonstrates both manual and automatic transitions, as well as how to
    define entry behavior for specific states.

    States:
        - A: Custom state with entry behavior
        - B, C, D: Generic states
        - FinalState: Terminal state

    Transitions:
        - A → B: Manual
        - B → C: Manual
        - C → D: Automatic
        - D → FinalState: Manual
    """
    def __init__(self, context: MyContext):
        super().__init__(context)

        # Define states
        a = StateA()
        b = State()
        c = State()
        d = State()
        final_state = FinalState()

        # Define transitions
        self._from_a_to_b = self.connect(a, b)                          # Manual
        self._from_b_to_c = self.connect(b, c, lambda ctx: print(ctx))  # Manual
        self.connect(c, d, automatic=True)                              # Automatic
        self.finish = self.connect(d, final_state)                      # Manual

        # Sets the initial state of the machine.
        self.initial_state = a

    def from_a_to_b(self):
        self._from_a_to_b.trigger()

    def from_b_to_c(self):
        self._from_b_to_c.trigger()

    # This method is replaced with a Transition object. Transition objects
    # can be called as they implement __callable interface. finnish() is
    # defined as an empty function to help IDEs like PyCharm with code completion.
    def finish(self): pass

    def on_state_changed(self, from_state: State, to_state: State):
        """Hook called after every state change."""
        print(f"State changed: {from_state} → {to_state}.")


# Instantiate and start the state machine
sm = MyStateMachine(context=MyContext())
sm.start()

# Wait until the machine enters state A, then manually trigger A → B
# sm.wait(sm.a)
sm.from_a_to_b()

# Manually trigger B → C
sm.from_b_to_c()

# C → D is automatic; wait for the next state change
sm.wait_next_state(timeout=5.0)

# Print current state after automatic transition
print(f"Current state: {sm.state}")

# Manually trigger D → FinalState
sm.finish()

# Wait for the machine to reach its final state
sm.join()

# Optional: render the state diagram in a browser
# from statemachine.diagram import show_state_diagram
# show_state_diagram(sm)
