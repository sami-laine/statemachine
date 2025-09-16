import threading
import time

import pytest

from statemachine import AlreadyStartedError
from statemachine import ErrorInfo, StateError
from statemachine import FinalState
from statemachine import InitialStateNotSetError
from statemachine import InvalidTransitionError
from statemachine import NotAliveError
from statemachine import State
from statemachine import StateMachine


class FailingState(State):
    MESSAGE = "crash"

    def on_entry(self, context):
        raise RuntimeError(self.MESSAGE)


class ABStateMachine(StateMachine):
    def __init__(self):
        super().__init__()

        self.a = State()
        self.b = FinalState()

        self.ab = self.connect(self.a, self.b)

        self.initial_state = self.a


class ABCStateMachine(StateMachine):
    def __init__(self):
        super().__init__()

        self.a = State()
        self.b = State()
        self.c = FinalState()

        self.ab = self.connect(self.a, self.b)
        self.bc = self.connect(self.b, self.c)
        self.reset = self.add_global_transition(self.a)

        self.initial_state = self.a


class AutomaticStateMachine(StateMachine):
    def __init__(self):
        super().__init__()

        self.initial_state = State()
        self.final_state = FinalState()

        self.connect(self.initial_state, self.final_state, automatic=True)


def test_initial_state():
    class Machine(StateMachine):
        def __init__(self):
            super().__init__()

            self.a = State()
            self.b = FinalState()

    sm = Machine()
    with pytest.raises(InitialStateNotSetError):
        sm.start()


def test_manual_transitions():
    sm = ABStateMachine()
    assert sm.initial_state is sm.a
    sm.start()
    sm.ab()
    assert sm.state == sm.b
    assert sm.join()


def test_automatic_transitions():
    sm = AutomaticStateMachine()
    sm.start()
    sm.join()

    assert sm.state is sm.final_state


def test_global_transition():
    sm = ABCStateMachine()
    sm.start()
    sm.ab()

    assert sm.state == sm.b

    sm.reset()

    assert sm.state == sm.a


def test_on_state_changed_callback():
    class MyStateMachine(ABStateMachine):
        def on_state_changed(self, from_state: State, to_state: State):
            assert from_state is self.a
            assert to_state is self.b

    sm = MyStateMachine()
    sm.start()
    sm.ab()
    sm.join()


def test_start():
    sm = ABStateMachine()
    sm.start()

    with pytest.raises(AlreadyStartedError):
        sm.start()

    sm.stop()
    assert sm.join(1.0) == True

    with pytest.raises(AlreadyStartedError):
        sm.start()


def test_stop():
    sm = ABStateMachine()

    with pytest.raises(NotAliveError):
        sm.stop()

    sm.start()
    sm.stop()
    sm.stop()
    sm.join(timeout=1.0)
    sm.stop()


def test_halt_and_resume():
    sm = ABStateMachine()
    sm.start()
    assert sm.is_halted() == False
    sm.halt()
    assert sm.is_halted() == True
    sm.resume()
    assert sm.is_halted() == False
    sm.stop()
    sm.join()
    assert sm.is_halted() == False


def test_is_alive():
    sm = ABStateMachine()

    with pytest.raises(NotAliveError):
        sm.halt()

    with pytest.raises(NotAliveError):
        sm.resume()

    with pytest.raises(NotAliveError):
        sm.stop()

    with pytest.raises(NotAliveError):
        sm.join()

    assert sm.is_alive() == False
    sm.start()
    assert sm.is_alive() == True
    sm.stop()
    assert sm.join(1.0) == True
    assert sm.is_alive() == False
    assert sm.join(1.0) == True


def test_invalid_transition():
    sm = ABCStateMachine()
    sm.start()

    assert sm.state == sm.a

    with pytest.raises(InvalidTransitionError):
        sm.bc()

    assert sm.is_halted() == False
    sm.stop()
    assert sm.join(1.0) == True


def test_error_handler():

    class MyStateMachine(StateMachine):
        def __init__(self):
            super().__init__()

            self.a = State()
            self.b = FailingState()
            self.ab = self.connect(self.a, self.b)
            self.initial_state = self.a
            self.error_info = None

        def handle_error(self, error_info: ErrorInfo):
            self.error_info = error_info

    sm = MyStateMachine()
    sm.start()

    with pytest.raises(StateError):
        sm.ab()

    assert sm.error_info.error is RuntimeError
    assert sm.error_info.value is FailingState.MESSAGE
    assert sm.is_halted() == True
    sm.resume()
    assert sm.is_halted() == False
    sm.stop()
    assert sm.join(1.0) == True


def test_wait():
    state_c_is_set_correctly = threading.Event()

    def wait_c():
        sm.wait(sm.c, 1.0)
        if sm.state is sm.c:
            state_c_is_set_correctly.set()

    sm = ABCStateMachine()
    sm.start()

    threading.Thread(target=wait_c, daemon=True).start()

    sm.ab()
    time.sleep(0.1)
    assert not state_c_is_set_correctly.is_set()

    sm.bc()
    time.sleep(0.1)
    assert state_c_is_set_correctly.is_set()

    sm.join()
