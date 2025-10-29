import logging
import time
import threading

from statemachine import StateMachine, State, T
from statemachine import FinalState


# Configure logging to show state transitions and timing info
logging.basicConfig(
    format=" %(name)-12s [%(levelname)-5s] %(message)s", level=logging.INFO
)
logger = logging.getLogger("Example")


class DelayedState(State):
    """A custom state that simulates a delay before completing.

    The state waits for a specified duration (or until it is exited early)
    before allowing the transition to proceed. This is useful for modeling
    time-based or interruptible states.
    """

    def __init__(self, delay: float, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._completed = threading.Event()  # Used to block or release the state
        self.delay = delay

    def prepare_entry(self, context: T):
        # Reset the completion flag before entering the state
        self._completed.clear()

    def on_exit(self, context: T):
        # Mark the state as completed when exiting early
        self._completed.set()

    def on_entry(self, context: T):
        # Wait for the delay to complete or for an early exit signal
        t = time.time()
        logger.info(f"State gets completed in {self.delay} seconds - or on exit.")
        self._completed.wait(self.delay)
        logger.info(f"State was completed in {time.time() - t:.1f} seconds.")


class ExampleMachine(StateMachine):
    """
    A simple state machine with a delayed state and a final state.

    The machine starts in the initial state, automatically transitions to
    a DelayedState, and then proceeds to a FinalState.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define states
        self.delayed_state = DelayedState(delay=2.0)
        self.final_state = FinalState()

        # Define transitions
        # Automatically move from the initial state to the delayed state
        self.connect(self.initial_state, self.delayed_state, automatic=True)

        # Automatically move from the delayed state to the final state
        self.finalise = self.connect(
            self.delayed_state, self.final_state, automatic=True
        )

    def on_state_changed(self, from_state: State, to_state: State):
        """Log every state transition."""
        logger.info(f"State changed: {from_state} → {to_state}.")


# Instantiate and start the state machine
sm = ExampleMachine()
sm.start()

# Wait until the machine reaches the delayed state, then execute the block atomically.
# Inside the block, we can choose to trigger the transition to the final state early.
#
# If `sm.finalise()` is called here, it will interrupt the delay and move to the final state.
# If it's commented out, the machine will wait for the full delay (2 seconds) before transitioning.
with sm.when(sm.delayed_state):
    sm.finalise()  # Comment this out to let the delay complete naturally
    pass

# Wait for the machine to finish all transitions and stop
sm.join()

logger.info("Done.")
