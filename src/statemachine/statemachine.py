import logging
import threading
import time
from functools import partial
from threading import Lock
from traceback import format_tb
from typing import Callable
from typing import Generic
from typing import Optional

from . import T
from .errors import AlreadyStartedError
from .errors import ErrorInfo
from .errors import FinalStateReached
from .errors import Halted
from .errors import InitialStateNotSetError
from .errors import InvalidTransitionError
from .errors import NoTransitionAvailable
from .errors import NotAliveError
from .errors import StateError
from .errors import TransitionError
from .state import FinalState
from .state import State
from .transition import GlobalTransition
from .transition import Transition

logger = logging.getLogger(__name__)


class StateMachine(Generic[T]):
    """State machine.

    Usage:
        class Door(StateMachine):
            def __init__(self):
                opened = Opened()
                closed = Closed()

                self.open = self.connect(closed, opened)
                self.close = self.connect(opened, closed)

        state_machine = Door(opened)
        state_machine.close()
        state_machine.open()
        ...
        state_machine.stop()
        state_machine.join()
    """

    def __init__(self, context: Optional[T] = None):
        self.context: Optional[T] = context

        # Only one thread is allowed to call on_exit() or on_entry() for a state
        # at the same time. These methods are called in subsequent order for a state.
        # _outer_lock and _inner_lock forms a chained structure where a thread
        # first acquires _outer_lock and then _inner_lock before releasing _outer_lock.
        # This arrangement allows two subsequent threads to call on_exit() and on_entry()
        # alternately.
        self._outer_lock = Lock()
        self._inner_lock = Lock()
        self._control_thread = None
        self._state_set_condition = threading.Condition()
        self._state_changed_condition = threading.Condition()
        self._run = threading.Event()
        self._stop = threading.Event()
        self.initial_state: Optional[State] = None
        self._current_state: Optional[State] = None
        self._transitions: list[Transition] = []

    def __str__(self):
        return self.__class__.__name__

    def __contains__(self, state: State):
        return self.state is state

    def connect(
        self,
        from_states: State | list[State],
        to_state: State,
        callback: Optional[Callable] = None,
        automatic: bool = False,
        name: Optional[str] = None,
    ) -> Transition:
        """Connect states.

        Creates a state transition that is allowed to occur from any of the given
        states (`from_states`) to the target state (`to_state`).

        Optionally user can give a callable that shall be called when this state
        transition occurs. The callable is called after exiting the previous state
        but before calling `on_entry()` for the applied state:

            * current_state.on_exit()
            * current_state = to_state
            * callback()
            * current_state.en_entry()

        Setting `automatic=True` allows the state machine to carry out
        the state transition automatically.

        Optional `name` argument can be used to give a name for the state transition.
        State machine does not use the name directly, but it can be helpful to follow
        state transitions and with visualisation.
        """
        transition = self.create_transition(
            from_states=from_states,
            to_state=to_state,
            automatic=automatic,
            name=name,
            callback=callback,
        )
        self.register_transition(transition)
        return transition

    def add_global_transition(
        self,
        to_state: State,
        callback: Optional[Callable] = None,
        automatic: bool = False,
        name: Optional[str] = None,
    ) -> Transition:
        """Add a global transition.

        Add a global transition from any state to given state. Otherwise, works the same as
        `connect()`.
        """
        transition = self.create_global_transition(
            to_state=to_state, automatic=automatic, name=name, callback=callback
        )
        self.register_transition(transition)
        return transition

    def create_transition(
        self,
        from_states: State | list[State],
        to_state: State,
        automatic: bool = False,
        name: str = None,
        callback: Optional[Callable] = None,
    ) -> Transition:
        """Create transition instance."""
        transition = Transition(
            from_states=from_states,
            to_state=to_state,
            automatic=automatic,
            name=name,
            callback=callback,
        )
        transition.trigger = partial(self.trigger, transition)
        return transition

    def create_global_transition(
        self,
        to_state: State,
        automatic: bool = False,
        name: str = None,
        callback: Optional[Callable] = None,
    ) -> Transition:
        """Create transition instance."""
        transition = GlobalTransition(
            to_state=to_state, automatic=automatic, name=name, callback=callback
        )
        transition.trigger = partial(self.trigger, transition)
        return transition

    def register_transition(self, transition: Transition):
        """Register a transition."""
        if not isinstance(transition, Transition):
            raise ValueError(f"Expecting Transition but got {transition}.")
        self._transitions.append(transition)

    def _log_states(self):
        log = [f"{self} states and transitions:"]
        for t in self.transitions():
            from_states = t.from_states[0] if len(t.from_states) == 1 else t.from_states
            if t.name:
                log.append(f"  {from_states} → {t.to_state} : {t.name}")
            else:
                log.append(f"  {from_states} → {t.to_state}")
        logger.debug("\n".join(log))

    def transitions(self) -> list[Transition]:
        """Get transitions as a list."""
        return self._transitions

    def _automatic_transitions(self) -> list[Transition]:
        """Get automatic transitions."""
        return [t for t in self.transitions() if t.automatic]

    def is_alive(self) -> bool:
        """Is state machine alive.

        Returns True is state machine has been started and not completed.
        """
        return self._control_thread is not None and self._control_thread.is_alive()

    def is_halted(self) -> bool:
        """Is state machine halted.

        State machine can be halted e.g., if state transition fails.
        """
        return not self._run.is_set()

    def start(self):
        """Start state machine.

        Starts the state machine and calls on_entry() of the initial state.
        on_state_changed() callback is not called.
        """
        with self._outer_lock:
            if self.is_alive() or self._control_thread is not None:
                raise AlreadyStartedError

            if self.initial_state is None:
                raise InitialStateNotSetError

            self._current_state = self.initial_state
            self._log_states()

            controller = self._control_loop

            self.on_start()

            try:
                self._current_state.on_entry(self.context)
            except FinalStateReached:
                controller = lambda: None

            self._run.set()
            self._control_thread = threading.Thread(target=controller, daemon=True)
            self._control_thread.start()

    def stop(self):
        """Stop state machine."""
        logger.debug("Stop state machine.")

        if self._stop.is_set():
            return

        if not self.is_alive():
            raise NotAliveError

        self._stop.set()

        with self._state_set_condition:
            self._state_set_condition.notify()

    def join(self, timeout: Optional[float] = None) -> bool:
        """Wait state machine to get completed.

        Returns False if a timeout is given and state machine didn't stop
        within the given wait time.
        """
        logger.debug("Wait state machine.")
        if self._control_thread is None:
            raise NotAliveError
        self._control_thread.join(timeout=timeout)
        return not self._control_thread.is_alive()

    def wait_next_state(self, timeout: Optional[float] = None) -> bool:
        """
        The return value is True unless a given timeout expired, in which case it is False.
        """
        with self._state_changed_condition:
            return self._state_changed_condition.wait(timeout)

    def wait(
        self, states: State | list[State], timeout: Optional[float] = None
    ) -> bool:
        """Wait a state to be applied.

        The return value is True unless a given timeout expired, in which case it is False.
        """
        states = states if isinstance(states, list) else [states]

        while not self.state in states:
            t = time.time()

            if self.wait_next_state(timeout) is False:
                return False

            if timeout is not None:
                timeout -= time.time() - t
                if timeout < 0:
                    return False

        return True

    def halt(self):
        """Halt the state machine momentarily.

        See resume() also.
        """
        logger.debug("Halt state machine.")
        if not self.is_alive():
            raise NotAliveError
        self._run.clear()

    def resume(self):
        """Resume state machine execution.

        See halt() also.
        """
        logger.debug("Resume state machine.")
        if not self.is_alive():
            raise NotAliveError
        self._run.set()

    def can_transition(self, transition: Transition) -> bool:
        """Check if a transition can be done.

        Checks if a state transition is valid and possible at this moment.
        """
        return transition.can_transition_from(self.state) and transition.is_applicable(
            self.context
        )

    def get_next_transition(self) -> Optional[Transition]:
        """Get next transition.

        Responsible to determine and return the next transition or None if
        no transition is available.
        """
        for t in self._automatic_transitions():
            try:
                if self.can_transition(t):
                    return t
            except Exception as error:
                logger.exception(error)
        return None

    def handle_next_transition(self):
        """Handle next transition.

        Responsible to trigger next state transition if any available. Handler
        is called by the internal control loop after a state transition is
        completed.

        Default implementation uses get_next_transition() to get the next
        available transition and trigger it.
        """
        if transition := self.get_next_transition():
            self.trigger(transition)
        else:
            raise NoTransitionAvailable

    def _control_loop(self):
        logger.debug("Control loop running.")

        with self._state_set_condition:
            while not self._stop.is_set():
                logger.debug("Handling next transition.")

                # State machine is halted and needs to be resumed before continuing.
                self._run.wait()

                try:
                    self.handle_next_transition()
                except NoTransitionAvailable:
                    logger.debug(
                        "No automatic transition available from %s." % self.state
                    )
                    logger.debug("Waiting manual state transition ...")
                    self._state_set_condition.wait()
                    logger.debug("Continuing after waiting state transition.")
                except TransitionError as error:
                    logger.exception(error)
                    self.halt()
                except (InvalidTransitionError, Halted) as error:
                    # Most likely a state machine has faces a race condition while
                    # handling a next transition.
                    logger.warning(error)
                except StateError as error:
                    logger.warning(error)
                except Exception as error:
                    logger.error(
                        "Error occurred while carrying out a state transition: %s",
                        error,
                    )

                # Other thread is already reserved the lock for trigger. Wait until
                # the tread is complete and new state is set.
                while self._outer_lock.locked() or self._inner_lock.locked():
                    self._state_set_condition.wait(10.0)

        logger.debug("Exiting control loop.")

        self.on_exit()

    def _handle_error(self, error_info: ErrorInfo) -> Optional[State]:
        logger.debug("Calling error handler.")

        try:
            state = self.handle_error(error_info)
            logger.debug("Calling error handler completed successfully.")
            return state
        except Exception as error:
            self.halt()
            logger.error("Calling error handler raised an error: %s", error)
            logger.exception(error)
        return None

    def handle_error(self, error_info: ErrorInfo) -> Optional[State]:
        """Handle error.

        This method is intended to be overwritten to implement custom error handler.
        Error handler is expected to resolve the error and resume the state machine.
        Error handler can also trigger a state transition.

        Default implementation is empty.
        """

    def handle_final_state_reached(self):
        """Handle final state reached."""
        logger.debug("Final state reached. Closing state machine.")
        self.stop()

    @property
    def state(self) -> State:
        """Current state machine state."""
        return self._current_state

    def trigger(self, transition: Transition):
        """Trigger a state transition."""

        try:
            logger.debug("Acquiring lock..")
            self._outer_lock.acquire()
            logger.debug("Lock acquired!")
            self._trigger(transition)
        except:
            if self._outer_lock.locked():
                self._outer_lock.release()
            raise

    def _trigger(self, transition: Transition):
        logger.debug(
            "Trigger state transition [%s]: %s → %s"
            % (transition.name, self.state, transition.to_state)
        )

        if not self.is_alive():
            raise NotAliveError

        if self.is_halted():
            raise Halted("State machine is halted.")

        if not transition.can_transition_from(self.state):
            raise InvalidTransitionError(
                f"Invalid state transition from '{self.state}' to '{transition.to_state}'."
            )

        try:
            self._call_on_exit_for(self._current_state)
            self._inner_lock.acquire()
            self._outer_lock.release()
            self._set_state(transition.to_state, transition.callback)
        except FinalStateReached:
            self.handle_final_state_reached()
        except Exception as error:
            logger.exception(error)
            self.halt()

            error_info = ErrorInfo(
                error=type(error),
                value=str(error),
                traceback="".join(format_tb(error.__traceback__)),
            )

            if next_state := self._handle_error(error_info):
                self._set_state(next_state)

            raise StateError() from error
        finally:
            self._inner_lock.release()

        logger.debug("State transition completed successfully.")

    def _set_state(self, state: State, callback: Callable = False):
        if state is None:
            raise ValueError("Cannot set state as None.")

        with self._state_set_condition:
            previous_state = self._current_state
            self._current_state = state

            logging.debug(f"State changed from '{previous_state}' to '{state}'.")

            self._call_on_state_changed(previous_state, state)

            with self._state_changed_condition:
                self._state_changed_condition.notify_all()

            try:
                self._call_callback(callback)
                self._call_on_entry_for(state)
                self._call_on_state_applied(state)

                if isinstance(state, FinalState):
                    raise FinalStateReached
            finally:
                self._state_set_condition.notify()

    def _call_on_state_changed(self, from_state: State, to_state: State):
        try:
            self.on_state_changed(from_state, to_state)
        except Exception as error:
            logger.warning("Calling on_state_changed() caused an error: %s", error)
            logger.exception(error)

    def _call_callback(self, callback: Callable):
        if callback is None:
            return
        logger.debug("Calling callback()' ...")
        callback(self.context)
        logger.debug("Calling callback()' completed successfully.")

    def _call_on_entry_for(self, state: State):
        logger.debug("Calling on_entry() for '%s' ...", state)
        state.on_entry(self.context)
        logger.debug("Calling on_entry() for '%s' completed successfully.", state)

    def _call_on_exit_for(self, state: State):
        logger.debug("Calling on_exit() for '%s' ...", state)
        state.on_exit(self.context)
        logger.debug("Calling on_exit() for '%s' completed successfully.", state)

    def _call_on_state_applied(self, state: State):
        try:
            self.on_state_applied(state)
        except Exception as error:
            logger.warning("Calling on_state_applied() caused an error: %s", error)
            logger.exception(error)

    def on_start(self):
        """Called on state machine start."""

    def on_exit(self):
        """Called on state machine exit."""

    def on_state_changed(self, from_state: State, to_state: State):
        """On state changed callback.

        Called after state has changed but before calling State.on_entry().
        """

    def on_state_applied(self, state: State):
        """Called when state has been applied.

        Called after successfully running state's on_entry() method.
        """
