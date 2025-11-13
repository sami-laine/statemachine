import time
import threading
import logging
from statemachine import State, StateMachine


# Configure logging
logging.basicConfig(
    format=" %(name)-12s [%(levelname)-5s] %(message)s", level=logging.INFO
)
logger = logging.getLogger("Door")


class Actuator:
    """Represents a physical actuator that opens and closes a door.

    This class is used as an example of a context object passed to
    states. It simulates extension (opening) and retraction
    (closing) with a delay.
    """

    logger = logging.getLogger("Actuator")

    def __init__(self, stroke_duration=2.0):
        self._ready = threading.Event()
        self._duration = stroke_duration  # Stroke duration in seconds.

    def extend(self):
        """Extend actuator (move outwards).

        Door is opened when actuator is extended.
        """
        Actuator.logger.info("Extending ...")
        self._ready.clear()
        self._ready.wait(self._duration)
        Actuator.logger.info("Extending ends.")

    def retract(self):
        """Retract actuator (pull inwards).

        Door is closed when actuator is retracted.
        """
        Actuator.logger.info("Retracting ...")
        self._ready.clear()
        self._ready.wait(self._duration)
        Actuator.logger.info("Retracting ends.")

    def stop(self):
        """Stop ongoing actuator movement."""
        Actuator.logger.info("Stop.")
        self._ready.set()


class Opening(State[Actuator]):
    """State representing the door opening process."""

    def on_entry(self, actuator: Actuator):
        actuator.extend()  # Blocks

    def on_exit(self, actuator: Actuator):
        # Stopping actuator ends extension.
        actuator.stop()


class Closing(State[Actuator]):
    """State representing the door closing process."""

    def on_entry(self, actuator: Actuator):
        actuator.retract()  # Blocks

    def on_exit(self, actuator: Actuator):
        # Stopping actuator ends retraction.
        actuator.stop()


class Opened(State[Actuator]):
    """State representing a state where the door is closed."""

    def __init__(self, keep_open_duration: float = 2.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._close = threading.Event()
        self._keep_open_duration = keep_open_duration

    def prepare_entry(self, context: Actuator):
        self._close.clear()

    def on_exit(self, context: Actuator):
        self._close.set()

    def on_entry(self, context: Actuator):
        logger.info("Keep door open for %s seconds.", self._keep_open_duration)
        self._close.wait(self._keep_open_duration)
        logger.info("Door can be closed.")


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
        self.opening = Opening()
        self.opened = Opened(keep_open_duration=2.0)
        self.closing = Closing()
        self.closed = State("Closed")

        # Define transitions
        self.connect(self.initial_state, self.opening, automatic=True)
        self._open = self.connect(
            [self.opening, self.closing, self.closed], self.opening, name="Open"
        )
        self._close = self.connect(
            [self.opening, self.opened, self.closing], self.closing, name="Close"
        )
        self.connect(self.opening, self.opened, automatic=True)
        self.connect(
            self.opened, self.closing, automatic=True
        )  # Door gets closed after a given delay.
        self.connect(self.closing, self.closed, automatic=True)
        self.connect(self.opening, self.opened)

    def open(self):
        logger.info("Open door.")
        self._open.trigger()

    def close(self):
        logger.info("Close door.")
        self._close.trigger()

    def on_state_changed(self, from_state: State, to_state: State):
        """Log state transitions."""
        logger.info(f"State changed: {from_state} → {to_state}.")


# Instantiate the state machine with an actuator context
door = DoorStateMachine(context=Actuator())
door.start()

# Wait for the first actual state to be applied. Without waiting,
# we may try to trigger `close` from the initial state.
door.wait(door.opening)

# Wait until the door reaches the 'opened' state.
# Without waiting the door begins closing before being opened.
# door.wait(door.opened)

# Trigger door closing in a separate thread. This demonstrates
# a multithreading use case.
threading.Thread(target=door.close).start()

# Trigger open while the door is still closing. A short delay is used
# to more likely avoid a situation where open() takes place before close().
time.sleep(0.2)
threading.Thread(target=door.open).start()

# Door remains opened for given time interval and then gets closed.
# Timeout can be used to ensure the waiting ends in given timeout.
door.wait(door.closed, timeout=8.0)

# Since there's no final state, we manually stop the state machine
door.stop()

# Wait for the state machine thread to exit cleanly
door.join()

# Log the final state
logger.info(f"Final state: {door.state}")
