import logging
import threading
import time
import types
from threading import Lock
from threading import RLock
from traceback import format_tb
from typing import Generic
from typing import Optional

from . import T
from .errors import AlreadyStartedError
from .errors import ConfigurationError
from .errors import ErrorInfo
from .errors import FinalStateReached
from .errors import Halted
from .errors import InvalidTransitionError
from .errors import NoTransitionAvailable
from .errors import NotAliveError
from .errors import StateError
from .errors import TransitionError
from .errors import StateMachineBusyError
from .state import InitialState
from .state import State
from .transition import Callback_Type
from .transition import GlobalTransition
from .transition import Transition

logger = logging.getLogger("StateMachine")


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
        self._outer_lock = RLock()
        self._inner_lock = Lock()
        self._control_thread = None
        self._state_set_condition = threading.Condition()
        self._state_changed_condition = threading.Condition()
        self._run = threading.Event()
        self._stop = threading.Event()
        self._initial_state: State = InitialState(name="InitialState")
        self._current_state: State = self.initial_state
        self._transitions: list[Transition] = []

    def __str__(self):
        return self.__class__.__name__

    def __contains__(self, state: State):
        return self.state is state

    @property
    def initial_state(self) -> State:
        return self._initial_state

    @initial_state.setter
    def initial_state(self, state: State):
        if not isinstance(state, State):
            raise TypeError(f"Expecting State but got {type(state)}.")
        self._initial_state = state

    def connect(
        self,
        from_states: State | list[State],
        to_state: State,
        name: Optional[str] = None,
        callback: Optional[Callback_Type] = None,
        automatic: bool = False,
    ) -> Transition:
        """Register a state transition between given states.

        connect() acts as a high-level convenience method. It wires together from_state,
        to_state, and an optional callback. It creates a state transition that is allowed
        to occur from any of the given states (`from_states`) to the target state
        (`to_state`).

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

        Calling connect() equals to:
            transition = Transition(from_states, to_state, automatic, name, callback)
            state_machine.add_transition(transition)

        Triggering transition manually:
            state_machine.trigger(transition)

        Returns the created transition object.
        """
        transition = self.create_transition(
            from_states=from_states,
            to_state=to_state,
            automatic=automatic,
            name=name,
            callback=callback,
        )
        self.add_transition(transition)
        return transition

    def connect_any(
        self,
        to_state: State,
        callback: Optional[Callback_Type] = None,
        automatic: bool = False,
        name: Optional[str] = None,
    ) -> Transition:
        """Connect from any state to this one.

        Add a global transition from any other state to given state. Otherwise, works the same as
        `connect()`.
        """
        transition = self.create_global_transition(
            to_state=to_state, automatic=automatic, name=name, callback=callback
        )
        self.add_transition(transition)
        return transition

    def create_transition(
        self,
        from_states: State | list[State],
        to_state: State,
        automatic: bool = False,
        name: Optional[str] = None,
        callback: Optional[Callback_Type] = None,
    ) -> Transition:
        """Create transition instance."""
        transition: Transition = Transition(
            from_states=from_states,
            to_state=to_state,
            automatic=automatic,
            name=name,
            callback=callback,
        )
        setattr(transition, "trigger", types.MethodType(self.trigger, transition))

        return transition

    def create_global_transition(
        self,
        to_state: State,
        automatic: bool = False,
        name: Optional[str] = None,
        callback: Optional[Callback_Type] = None,
    ) -> Transition:
        """Create global transition instance."""
        transition: Transition = GlobalTransition(
            to_state=to_state, automatic=automatic, name=name, callback=callback
        )
        setattr(transition, "trigger", types.MethodType(self.trigger, transition))
        return transition

    def add_transition(self, transition: Transition):
        """Register a transition object."""
        if not isinstance(transition, Transition):
            raise ValueError(f"Expecting Transition but got {transition}.")
        self._transitions.append(transition)

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

    def _log_states(self):
        lines = [f"{self} states and transitions:"]
        for t in self.transitions():
            from_states = f"[{', '.join([str(s) for s in t.from_states])}]"
            line = f"  {from_states} → {t.to_state}"
            if t.name:
                line += f" : {t.name}"
            if t.automatic:
                line += " (automatic)"
            lines.append(line)
        logger.debug("\n".join(lines))

    def _is_initial_state_used(self) -> bool:
        for t in self.transitions():
            if self.initial_state in t.from_states:
                return True
        return False

    def start(self):
        """Start state machine.

        Starts the state machine and calls on_entry() of the initial state.
        on_state_changed() callback is not called.
        """
        # with self._outer_lock:
        if self.is_alive() or self._control_thread is not None:
            raise AlreadyStartedError

        if not self._is_initial_state_used():
            raise ConfigurationError(
                "Initial state is not connected to any other state."
                "Use 'state_machine.connect(self.initial_state, other_state)' to connect."
            )

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
        logger.debug("Waiting control loop to get completed.")
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
        target_states = states if isinstance(states, list) else [states]
        timer = _CountdownTimer(timeout)

        while not self.state in target_states:
            logger.debug(
                "Waiting %s to occur. Timeout is set as %s." % (states, timeout)
            )

            if self.wait_next_state(timer.time_left) is False:
                return False

            if timer.expired():
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
        """Check if a transition can be done from given state.

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
            # May raise StateMachineBusyError.
            self.trigger(transition, blocking=False)
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
                    logger.debug("Waiting for external state transition ...")
                except StateMachineBusyError:
                    logger.debug(
                        "Failed to trigger a transition - busy serving another thread. Waiting ..."
                    )
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

                # Other thread is already in trigger(). Wait until the thread is
                # complete and new state is set. Waiting gives a change for external
                # threads to trigger a transition while the state machine is still
                # busy with long-lasting state logic.
                self._wait_busy()

        logger.debug("Exiting control loop.")

        self.on_exit()

    def _wait_busy(self, interval=0.1):
        while True:
            self._state_set_condition.wait(timeout=interval)
            if not self._inner_lock.locked():
                break

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
        """Current state machine state.

        Returns current state machine state unless not started then returns None.
        """
        return self._current_state

    def trigger(
        self,
        transition: Transition,
        blocking: bool = True,
        timeout: Optional[float] = None,
    ):
        """Trigger the given state transition.

        This method attempts to execute the specified transition. If the state machine
        is currently reserved by another thread, behavior depends on the `blocking` and
        `timeout` parameters.

        Args:
            transition (Transition): The transition to trigger.
            blocking (bool): If True (default), wait until the state machine becomes available.
                             If False, raise an error immediately if the machine is in use.
            timeout (float, optional): Maximum time in seconds to wait for the machine to become available.
                                       If None, wait indefinitely (when blocking=True).

        Raises:
            TransitionError: If `blocking` is False and the state machine is currently reserved.

        Usage:
            - `blocking=True` → Wait until the state machine is available (optionally with a timeout).
            - `blocking=False` → Try immediately and raise an error if unavailable.

        Transition Workflow:
            With outer lock:
                1. Check if transition is valid.
                2. Call `on_exit()` on the current state.

            With outer and inner lock:
                3. Invoke the transition's callback (if any).
                4. Set the new state.
                5. Call `prepare_entry()`.
                6. Call `on_state_changed()`.
                7. Notify threads waiting for a state change.

            With inner lock:
                8. Call `on_entry()` on the new state.
                9. Call `on_state_applied()`.
        """
        if blocking is False or timeout is None:
            # Lock.acquire(): It is forbidden to specify a timeout when blocking is False.
            timeout = -1

        if not self._outer_lock.acquire(blocking=blocking, timeout=timeout):
            raise StateMachineBusyError(
                f"Failed to trigger state transition (blocking={blocking} timeout={timeout}): "
                "Busy serving another thread."
            )

        try:
            logger.debug(
                "Triggering state transition [%s]: %s → %s"
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

            # Error in on_exit() prevents state transition - as well as
            # error in calling transition callback.
            self._call_on_exit(self._current_state)

            # Later thread must wait until the first one gets completed.
            self._inner_lock.acquire()
            self._call_transition_callback(transition)

            # Set state as current state and prepare it for entry.
            state = transition.to_state
            previous_state = self._current_state

            self._set_state(state)
            self._call_prepare_entry(state)

            # Notify about the change in state.
            self._call_on_state_changed(previous_state, state)
            self._notify_state_changed()
        except Exception:
            if self._inner_lock.locked():
                self._inner_lock.release()
            raise
        finally:
            self._outer_lock.release()

        # After releasing _outer_lock other thread may acquire it and call
        # on_exit() for the current state - unless current thread had already
        # acquired the lock already in use() or when() context managers.

        # Invoke the state specific logic. Failure in state logic keeps
        # the state unchanged until the error is handled.
        # The error handler is called also if final state fails.

        try:
            self._call_on_entry(state)
            self._call_on_state_applied(state)

            if state.final:
                raise FinalStateReached  # Raising FinalStateReached for single source of truth.
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
            with self._state_set_condition:
                self._state_set_condition.notify()

    def _set_state(self, state: State):
        previous_state = self._current_state
        self._current_state = state
        logger.debug(f"State changed from '{previous_state}' to '{state}'.")

    def _notify_state_changed(self):
        with self._state_changed_condition:
            self._state_changed_condition.notify_all()

    def _call_on_state_changed(self, from_state: State, to_state: State):
        try:
            self.on_state_changed(from_state, to_state)
        except Exception as error:
            logger.warning("Calling on_state_changed() caused an error: %s", error)
            logger.exception(error)

    def _call_transition_callback(self, transition: Transition):
        if not transition.callback:
            return
        logger.debug("Calling '%s' callback()' ...", transition)
        transition.callback(self.context)
        logger.debug("Calling '%s' callback()' completed.", transition)

    def _call_prepare_entry(self, state: State):
        logger.debug("Calling '%s' prepare_entry() ...", state)
        state.prepare_entry(self.context)
        logger.debug("Calling '%s' prepare_entry() completed.", state)

    def _call_on_entry(self, state: State):
        logger.debug("Calling '%s' on_entry() ...", state)
        state.on_entry(self.context)
        logger.debug("Calling '%s' on_entry() completed.", state)

    def _call_on_exit(self, state: State):
        logger.debug("Calling '%s' on_exit() ...", state)
        state.on_exit(self.context)
        logger.debug("Calling '%s' on_exit() completed.", state)

    def _call_on_state_applied(self, state: State):
        try:
            self.on_state_applied(state)
        except Exception as error:
            logger.warning("Calling on_state_applied() caused an error: %s", error)
            logger.exception(error)

    def use(self, blocking: bool = True, timeout: Optional[float] = None) -> "_Use":
        """Reserve the state machine for exclusive use by the current thread.

        This context manager ensures that a block of code executes atomically,
        preventing other threads from triggering transitions during its execution.

        Args:
            blocking (bool): If True (default), wait until the state machine becomes available.
                             If False, return immediately if the machine is already in use.
            timeout (float, optional): Maximum time in seconds to wait for the machine to become available.
                                       If None, wait indefinitely (when blocking=True).

        Returns:
            A context manager that locks the state machine for the duration of the block.

        Example:
            with sm.use():
                sm.transition_from_a_to_b()
                sm.transition_from_b_to_c()
        """
        return _Use(self, blocking=blocking, timeout=timeout)

    def when(
        self, states: State | list[State], timeout: Optional[float] = None
    ) -> "_When":
        """Wait until the state machine reaches one of the specified states, then reserve it for use.

        This context manager blocks until the machine enters the target state(s),
        then locks it for the current thread to safely execute a block of code.

        Args:
            states (State or list[State]): The state or list of states to wait for.
            timeout (float, optional): Maximum time in seconds to wait for the target state.
                                       If None, wait indefinitely.

        Returns:
            A context manager that waits for the state and locks the machine once reached.

        Example:
            with sm.when(sm.state_a):
               sm.transition_from_a_to_b()
        """
        return _When(state_machine=self, states=states, timeout=timeout)

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


class _Use:
    def __init__(
        self,
        state_machine: StateMachine,
        blocking: bool,
        timeout: Optional[float] = None,
    ):
        self._state_machine = state_machine
        self._blocking = blocking
        self._timeout = timeout

    def __enter__(self):
        sm = self._state_machine
        timeout = self._timeout if self._timeout is not None else -1
        sm._outer_lock.acquire(blocking=self._blocking, timeout=timeout)

    def __exit__(self, exc_type, exc_val, exc_tb):
        sm = self._state_machine
        sm._outer_lock.release()
        with sm._state_set_condition:
            sm._state_set_condition.notify_all()


class _When:
    def __init__(
        self,
        state_machine: StateMachine,
        states: State | list[State],
        timeout: Optional[float] = None,
    ):
        self._state_machine = state_machine
        self._states = states
        self._timeout = timeout

    def __enter__(self):
        sm = self._state_machine
        timer = _CountdownTimer(self._timeout)
        while sm.wait(self._states, timeout=timer.time_left):
            if sm._outer_lock.acquire(timeout=timer.time_left or -1):
                return sm.context
        raise TimeoutError(
            f"Waiting for {self._states} state(s) timed out in {self._timeout} seconds."
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        sm = self._state_machine
        sm._outer_lock.release()
        with sm._state_set_condition:
            sm._state_set_condition.notify_all()


class _CountdownTimer:
    def __init__(self, duration: Optional[float] = None):
        self.duration = duration
        self.start_time = time.time()

    def __str__(self) -> str:
        return str(self.time_left)

    @property
    def time_left(self) -> Optional[float]:
        if self.duration is None:
            return None
        return max(0.0, self.duration - (time.time() - self.start_time))

    def expired(self) -> bool:
        time_left = self.time_left
        if self.duration is None or time_left is None:
            return False
        return time_left <= 0
