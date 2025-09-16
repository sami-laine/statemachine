"""Simple example to demonstrate how to branch a control flow.

This state machine models a system where something (Data) gets processed.
The system may need to wait for the processing slot to become available.
The control flow branches from staging to processing or waiting state
depending on whether the processing state is available for use or not.

State machine determines whether a state can be applied by calling
States' is_applicable(). The method is expected to return True if the
state can be applied right now or False if not.
"""
import random
import time
from dataclasses import dataclass
from statemachine import State, FinalState, StateMachine


@dataclass
class Data:
    """Context object passed through the state machine.

    Tracks how many times data has been processed and how many times it had to wait.
    """
    value: int = 0
    wait_count: int = 0


class Processing(State[Data]):
    """State representing active data processing.

    This state may not always be available. The state machine checks its applicability
    before transitioning into it.
    """

    def is_applicable(self, data: Data) -> bool:
        """Determine whether the processing slot is available.

        Simulates availability by randomly returning True (available) or False (busy).
        """
        ready = random.randrange(1, 5) == 1
        print(f"Ready to begin processing: {ready}")
        return ready

    def on_entry(self, data: Data):
        """Increment the processed value count."""
        data.value += 1


class Waiting(State[Data]):
    """State representing a short wait before retrying processing."""

    def on_entry(self, data: Data):
        """Increment wait count and simulate a brief delay."""
        data.wait_count += 1
        time.sleep(0.01)


class MyStateMachine(StateMachine[Data]):
    """State machine that branches based on processing availability.

    States:
        - staging: Entry point for each cycle
        - processing: Attempts to process data (conditionally applicable)
        - waiting: Temporary waiting state before retry
        - final_state: Terminal state after successful processing

    Transitions:
        - staging → processing (if applicable)
        - staging → waiting (fallback)
        - waiting → staging (retry loop)
        - processing → final_state (completion)
    """
    def __init__(self, context: Data):
        super().__init__(context)
        # Define states
        staging = State()
        processing = Processing()
        waiting = Waiting()
        final_state = FinalState()

        # Set the initial state
        self.initial_state = staging

        # Define automatic transitions
        self.connect(staging, processing, automatic=True, name="process")
        self.connect(staging, waiting, automatic=True, name="wait")
        self.connect(waiting, staging, automatic=True, name="stage")
        self.connect(processing, final_state, automatic=True, name="ready")

    def on_state_changed(self, from_state: State, to_state: State):
        """Log state transitions."""
        print(f"State changed: {from_state} → {to_state}.")


# Create context object to track processing and waiting
data = Data()

# Instantiate and start the state machine
sm = MyStateMachine(context=data)
sm.start()

# Wait for the state machine to reach its final state
sm.join()

# Output final context state
print(data)
