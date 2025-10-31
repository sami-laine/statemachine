import threading
import pytest
from statemachine import StateMachine, State


class Machine(StateMachine):
    def __init__(self):
        super().__init__()
        self.a = State("A")
        self.b = State("B")
        self.c = State("C")
        self.d = State("D")

        self.a_to_b = self.connect(self.a, self.b)
        self.b_to_c = self.connect(self.b, self.c)
        self.connect(self.c, self.d, automatic=True)

        self.initial_state = self.a

    def on_state_changed(self, from_state, to_state):
        self.last_transition = (from_state, to_state)


@pytest.fixture
def state_machine():
    machine = Machine()
    machine.start()
    return machine


def test_basic_transition(state_machine):
    state_machine.a_to_b()
    assert state_machine.state == state_machine.b


def test_use_context_manager(state_machine):
    with state_machine.use():
        state_machine.a_to_b()
        state_machine.b_to_c()
    assert state_machine.state == state_machine.c


def test_when_context_manager(state_machine):
    state_machine.a_to_b()
    state_machine.b_to_c()

    def wait_and_check():
        with state_machine.when(state_machine.d):
            assert state_machine.state == state_machine.d

    thread = threading.Thread(target=wait_and_check)
    thread.start()
    thread.join(timeout=2)


def test_thread_safety_with_use(state_machine):
    results = []

    def thread_job():
        with state_machine.use():
            state_machine.a_to_b()
            results.append(state_machine.state)

    thread = threading.Thread(target=thread_job)
    thread.start()
    thread.join()

    assert state_machine.b in results


def test_state_change_callback(state_machine):
    state_machine.a_to_b()
    assert state_machine.last_transition == (state_machine.a, state_machine.b)
