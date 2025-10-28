import itertools
import logging
from typing import Generic
from typing import Optional

from . import T
from .errors import FinalStateReached


logger = logging.getLogger(__name__)


class State(Generic[T]):
    """State represents a state machine state.

    Usage:
        class Example(State[Context]):
            def is_applicable(self, context: Context) -> bool:
                return True

            def on_entry(self, context: Context):
                pass

            def on_exit(self, context: Context):
                pass
    """

    _name: Optional[str] = None
    _state_counter = itertools.count(1)

    def __init__(self, name: Optional[str] = None):
        state_number = next(self._state_counter)
        self.name = name or self._name or f"S{state_number}"

    def __init_subclass__(cls, name=None):
        cls._name = name or cls.__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def is_applicable(self, context: T) -> bool:
        """Can the state be applied now.

        Implies that the state can be applied right now, assuming all conditions are met.
        """
        return True

    def on_entry(self, context: T):
        """Called when state machine enters this state.

        StateMachine.state is set just before calling this function. So, calling
        StateMachine.state == self would return True.
        """

    def on_exit(self, context: T):
        """Called just before state machine exits this state.

        State transition does not occur if calling on_exit() causes an error.
        Caller must handle the exception. The caller can also trigger a state
        transition into an error state.
        """


class InitialState(State):
    """Default initial state."""


class FinalState(State):
    """Default final state.

    Raises FinalStateReached exception that closes the state machine.
    """

    def on_entry(self, context: T):
        raise FinalStateReached


class AnyState(State):
    """Matches any state.

    Used by GlobalTransition.
    """

    def __eq__(self, other):
        return isinstance(other, State)

    def __repr__(self):
        return "*"
