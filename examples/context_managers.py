"""Thread-Safe State Transitions with use() and when()

This example demonstrates how to use a custom StateMachine with thread-safe context managers:

* use() allows you to reserve the state machine for a block of operations, ensuring transitions
  and logic execute atomically.
* when(state) waits for a specific state and then runs code safely once that state is reached.
"""

import logging

from statemachine import StateMachine, State


logging.basicConfig(
    format=" %(name)-12s [%(levelname)-5s] %(message)s", level=logging.INFO
)
logger = logging.getLogger("Door")


class ExampleMachine(StateMachine):
    def __init__(self, context: str):
        super().__init__(context=context)

        # Define states
        self.a = State(name="A")
        self.b = State(name="B")
        self.c = State(name="C")
        self.d = State(name="D")

        # Define transitions
        self.a_to_b = self.connect(self.a, self.b)
        self.b_to_c = self.connect(self.b, self.c)
        self.connect(self.c, self.d, automatic=True)

        # _Use 'A' as the initial state.
        self.initial_state = self.a

    def on_state_changed(self, from_state: State, to_state: State):
        """Hook called after every state change."""
        logger.info(f"State changed: {from_state} → {to_state}.")


def main():
    # Instantiate and start the machine
    sm = ExampleMachine(context="Hello")
    sm.start()

    # Use 'with sm.use()' to reserve the state machine for the current thread.
    # This ensures that all operations within the block execute atomically,
    # without interference from other threads.
    #
    # It's ideal for performing multiple transitions or actions in a controlled sequence.
    #
    # While you can subclass State and override on_entry() to run logic during transitions,
    # 'use()' offers more flexibility—for example, when executing dynamic or conditional logic.
    #
    # The state machine remains reserved until the end of the 'with' block.
    with sm.use():
        sm.a_to_b()
        logger.info("Code to be run in 'B'.")
        sm.b_to_c()

    logger.info("Waiting 'D' ...")

    # The transition from 'C' to 'D' is automatic.
    #
    # Use 'with sm.when(state)' to wait until the machine reaches the specified state(s),
    # and then execute a block atomically—similar to 'use()', but triggered by state arrival.
    #
    # While 'sm.wait()' can also wait for a state, it doesn't guarantee atomicity.
    # The state might change before the next action is executed.
    #
    # 'when()' solves this by locking the machine as soon as the target state is reached.
    with sm.when(sm.d):
        logger.info("Code to run in 'D'.")
        sm.stop()

    sm.join()

    logger.info("Done.")


main()
