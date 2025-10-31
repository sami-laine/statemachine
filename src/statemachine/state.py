import itertools
import logging
from typing import Generic
from typing import Optional
from typing import Callable

from . import T
from .errors import FinalStateReached


logger = logging.getLogger(__name__)


Callback_Type = Callable[[Optional[T]], None]


class State(Generic[T]):
    """State represents a state machine state.

    Usage:
        class Example(State[Context]):
            def is_applicable(self, context: Context) -> bool:
                return True

            def prepare_entry(self, context: Context):
                pass

            def on_entry(self, context: Context):
                pass

            def on_exit(self, context: Context):
                pass
    """

    _name: Optional[str] = None
    _state_counter = itertools.count(1)

    def __init__(
        self,
        name: Optional[str] = None,
        callback: Optional[Callback_Type] = None,
        final: bool = False,
    ):
        state_number = next(self._state_counter)
        self.name = name or self._name or f"S{state_number}"
        self.final = final
        self._callback = (lambda _: None) if callback is None else callback

    def __init_subclass__(cls, name=None):
        cls._name = name or cls.__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def is_applicable(self, context: T) -> bool:
        """Can the state be applied now.

        Implies that the state can be applied right now, assuming all conditions
        are met.
        """
        return True

    def prepare_entry(self, context: T):
        """Called before `on_entry()` to prepare the state for activation.

        This method is intended for resetting internal state or performing
        lightweight setup before the state becomes active. It should complete
        quickly. The main state-specific logic should be implemented in `on_entry()`.

        In multithreaded environments, `on_exit()` may be called before `on_entry()`
        - this is important to consider when designing interruptible states.
        `prepare_entry()` is guaranteed to be invoked before either `on_entry()` or
        `on_exit()`.
        """

    def on_entry(self, context: T):
        """Called when state machine enters this state.

        At this point, `StateMachine.state` has already been updated, so
        `StateMachine.state == self` will return True.

        This method is intended for implementing the main logic that should run
        when the state becomes active.

        Note:

        In multithreaded environments, `on_exit()` may be called before `on_entry()`.
        This is important to consider when designing interruptible states.

        The `prepare_entry()` method is guaranteed to be called before either
        `on_entry()` or `on_exit()`.
        """
        self._callback(context)

    def on_exit(self, context: T):
        """Called before state machine exits this state.

        This method allows for cleanup or finalization logic before transitioning away
        from the current state. If `on_exit()` raises an exception, the transition will
        be aborted. The caller is responsible for handling the exception and may choose
        to trigger a transition into an error state.

        Note:

        In multithreaded environments, `on_exit()` may be called before `on_entry()`
        - this is important to consider when designing interruptible states.
        `prepare_entry()` is guaranteed to be invoked before either `on_entry()` or
        `on_exit()`.
        """


class InitialState(State):
    """Default initial state."""


class FinalState(State):
    """A default final state that terminates the state machine when entered.

    This state is marked as final and is intended to signal the end of the state
    machine's lifecycle. No further transitions should occur after it is entered.

    Note:
        You can also use `State(final=True)` to mark any state as final.
        Raising `FinalStateReached` manually from `on_exit()` will have the same
        effect. `FinalState` simply provides a convenient default implementation.

    Args:
        name (str): Optional name for the final state. Defaults to "Final".
    """

    def __init__(self, name: str = "Final"):
        super().__init__(name=name, final=True)


class AnyState(State):
    """Matches any state.

    Used by GlobalTransition.
    """

    def __eq__(self, other):
        return isinstance(other, State)

    def __repr__(self):
        return "*"
