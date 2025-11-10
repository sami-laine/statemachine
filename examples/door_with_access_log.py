from time import sleep
from datetime import datetime
from dataclasses import dataclass
from statemachine import StateMachine, State


class Opened(State):
    def on_entry(self, access_log: list):
        # Log the time when the door enters the 'Opened' state
        access_log.append(Entry(self.name, datetime.now().isoformat()))


class Closed(State):
    def on_entry(self, access_log: list):
        # Log the time when the door enters the 'Closed' state
        access_log.append(Entry(self.name, datetime.now().isoformat()))


class Door(StateMachine[list]):
    def __init__(self, access_log: list):
        super().__init__(context=access_log)

        # Define states
        self.closed = Closed("Closed")
        self.closing = State("Closing", lambda _: sleep(1.0))
        self.opening = State("Opening", lambda _: sleep(1.0))
        self.opened = Opened("Opened")
        self.locked = State("Locked")

        # Define transitions
        self.open = self.connect(self.closed, self.opening, "Open")
        self.close = self.connect(self.opened, self.closing, "Close")
        self.lock = self.connect(self.closed, self.locked, "Lock")
        self.unlock = self.connect(self.locked, self.closed, "Unlock")
        self.connect(self.opening, self.opened, automatic=True)
        self.connect(self.closing, self.closed, automatic=True)

        # Use 'Closed' state as an initial state.
        self.initial_state = self.closed

    def on_state_changed(self, from_state: State, to_state: State):
        print(f"State changed: {from_state} → {to_state}")


@dataclass
class Entry:
    """Access log entry."""
    event: str
    when: str


# Naive example of an access log. Access log is used as a state machine context.
# Context objects may hold e.g., data, resources or control structures.
access_log: list = []

# Instantiate and start the machine.
door = Door(access_log)
door.start()
door.open()

# Wait until the door is opened, then close it.
with door.when(door.opened):
    door.close()

# Wait until the door is closed.
door.wait(door.closed)

# Reserve the state machine for use.
with door.use():
    door.lock()
    # Code to run while the door is locked and closed.
    door.unlock()

# Stop the state machine.
door.stop()
door.join()

# Print the access log.
for entry in access_log:
    print(f"Event: {entry.event}, Time: {entry.when}")
