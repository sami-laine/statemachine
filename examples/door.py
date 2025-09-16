import threading
import logging
from statemachine import State, StateMachine


# Configure logging
logging.basicConfig(format='%(levelname)s %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


class Actuator:
    """Represents a physical actuator that opens and closes a door.

    This class is used as an example of a context object passed to
    states. It simulates extension (opening) and retraction
    (closing) with a delay.
    """
    def __init__(self):
        self._stop = threading.Event()
        self._duration = 1.0  # Simulated movement duration in seconds

    def extend(self):
        """Simulate extending the actuator (opening the door)."""
        self._stop.clear()
        self._stop.wait(self._duration)

    def retract(self):
        """Simulate retracting the actuator (closing the door)."""
        self._stop.clear()
        self._stop.wait(self._duration)

    def stop(self):
        """Cancel any ongoing actuator movement."""
        self._stop.set()


class Opening(State[Actuator]):
    """State representing the door opening process."""

    def on_entry(self, actuator: Actuator):
        logger.info("Door is opening ...")
        actuator.extend()
        logger.info("Opening ended.")

    def on_exit(self, actuator: Actuator):
        # Stop actuator if transition occurs before completion
        actuator.stop()


class Closing(State[Actuator]):
    """State representing the door closing process."""

    def on_entry(self, actuator: Actuator):
        logger.info("Door is closing ...")
        actuator.retract()
        logger.info("Closing ended.")

    def on_exit(self, actuator: Actuator):
        actuator.stop()


class DoorStateMachine(StateMachine[Actuator]):
    """State machine controlling the door actuator.

    States:
        - opening: Actively opening the door
        - opened: Door is fully open
        - closing: Actively closing the door
        - closed: Door is fully closed

    Transitions:
        - open: Manual trigger to begin opening
        - close: Manual trigger to begin closing
        - _opening: Automatic transition from opening → opened
        - _closing: Automatic transition from closing → closed
    """
    def __init__(self, context: Actuator):
        super().__init__(context)

        # Define states
        opening = Opening()
        self.opened = State("Opened")
        closing = Closing()
        closed = State("Closed")

        # Use 'Opened' as initial state
        self.initial_state = self.opened

        # Define transitions
        self._open = self.connect([opening, self.opened, closing, closed], opening)
        self._close = self.connect([opening, self.opened, closing, closed], closing)
        self.connect(opening, self.opened, automatic=True)
        self.connect(closing, closed, automatic=True)

    def open(self):
        self._open.trigger()

    def close(self):
        self._close.trigger()

    def on_state_changed(self, from_state: State, to_state: State):
        """Log state transitions."""
        logger.info(f"State changed: {from_state} → {to_state}.")


# Instantiate the state machine with an actuator context
door = DoorStateMachine(context=Actuator())
door.start()

# Trigger door opening
door.open()

# Wait until the door reaches the 'opened' state.
# Without waiting the door begins closing before being opened.
# door.wait(door.opened)

# Trigger door closing in a separate thread.
threading.Thread(target=door.close).start()

# Optionally, trigger another open operation while the door is closing.
threading.Thread(target=door.open).start()

# Wait until the door reaches the 'opened' state.
door.wait(door.opened)

# Since there's no final state, we manually stop the state machine
door.stop()

# Wait for the state machine thread to exit cleanly
door.join()

# Log the final state
logger.info(f"Final state: {door.state}")
