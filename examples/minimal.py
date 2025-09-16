from statemachine import StateMachine, State, FinalState


class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()

        # Define states
        a = State()
        b = State()
        c = FinalState()

        # Define transitions
        self.a_to_b = self.connect(a, b)  # manual transition
        self.connect(b, c, automatic=True)  # automatic transition

        # Set initial state
        self.initial_state = a


# Instantiate and start the machine
sm = ExampleMachine()
sm.start()

# Trigger the manual transition from a → b
sm.a_to_b()

# Wait until the machine reaches the final state
sm.join()
