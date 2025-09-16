import logging
from dataclasses import dataclass
from typing import Optional

from statemachine import State, FinalState, StateMachine, ErrorInfo

# Configure logging
logging.basicConfig(format='%(levelname)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass
class Data:
    """Context object passed through the state machine.

    Contains a dummy fault flag that simulates a runtime error.
    """
    fault: bool = True


class Processing(State[Data]):
    """State representing a processing step that may fail."""

    def on_entry(self, data: Data):
        """Raise an error if the fault flag is set."""
        if data.fault:
            raise RuntimeError("Fault!")


class MyStateMachine(StateMachine[Data]):
    """State machine with error handling and recovery logic.

    States:
        - _initial_state: Starting point
        - processing: May raise an error based on context
        - final_state: Terminal state

    Transitions:
        - _initial_state → processing (automatic)
        - processing → final_state (automatic)
    """
    def __init__(self, context: Data):
        super().__init__(context)

        # Define states
        self.initial_state = State()
        self.processing = Processing()

        # Define transitions
        self.connect(self.initial_state, self.processing, automatic=True, name="process")
        self.connect(self.processing, FinalState(), automatic=True, name="finish")

    def get_initial_state(self) -> State:
        """Set the initial state to '_initial_state'."""
        return self.initial_state

    def on_state_changed(self, from_state: State, to_state: State):
        """Log state transitions."""
        print(f"State changed: {from_state} → {to_state}.")

    def handle_error(self, error_info: ErrorInfo) -> Optional[State]:
        """Custom error handler invoked when a transition fails.

        This method is called automatically when an exception is raised during
        a transition. It can log the error, resolve the issue, resume the machine,
        and optionally redirect to a new state.

        Error causes the state machine to get halted. This mechanism ensures that errors are
        detected and addressed before they escalate.

        State machine can be restored back to running state by calling resume(). State machine
        continues to process state transitions after returning from the error handler - unless
        resume() is not called.

        Error handler can resolve the issue, but it can also redirect the state machine toward
        the next desired state. This happens by returning the next state. For example,
        in this example error handler returns the state machine back to processing state.

        In some other use case the state machine could use a special error state to indicate
        the failure. The failure could be then shown on UI and resolved.

        Returns:
            Optional[State]: The next state to transition to, or None to continue.
        """
        print("Error info:")
        print(f"    State: {self.state}")
        print(f"    Error: {error_info.error.__name__}")
        print(f"    Message: {error_info.value}")

        # Example resolution: clear the fault if we're in the processing state
        if self.state is self.processing:
            self.context.fault = False

        # Resume the state machine after handling the error
        print(f"Is state machine halted: {self.is_halted()}")
        self.resume()
        print(f"Is state machine halted: {self.is_halted()}")

        # Optionally return a state to redirect the flow
        return self.processing


# Create context object with a fault
data = Data()

# Instantiate and start the state machine
sm = MyStateMachine(context=data)
sm.start()

# Wait for the state machine to reach its final state
sm.join()
