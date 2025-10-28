from typing import Callable
from typing import Generic
from typing import Optional
import itertools

from . import T
from .state import AnyState
from .state import State


Callback_Type = Callable[[Optional[T]], None]


class Transition(Generic[T]):
    """State transition."""
    _transition_counter = itertools.count(1)

    def __init__(
        self,
        from_states: State | list[State],
        to_state: State,
        automatic: bool = False,
        name: Optional[str] = None,
        callback: Optional[Callback_Type] = None,
    ):
        transition_number = next(self._transition_counter)
        self.from_states = (
            from_states if isinstance(from_states, list) else [from_states]
        )
        self.to_state = to_state
        self.automatic = automatic
        self.name = name or f"T{transition_number}"
        self.callback = callback

        for state in self.from_states:
            if not isinstance(state, State):
                raise ValueError(f"Expecting State, got {state}.")

        if not isinstance(to_state, State):
            raise ValueError(f"Expecting State, got {to_state}.")

    def __str__(self):
        return f"{self.name} [auto]" if self.automatic else f"{self.name} [manual]"

    def __call__(self, blocking: bool = True, timeout: Optional[float] = None):
        """Triggers the transition.

        Calls trigger() internally.
        """
        self.trigger(blocking=blocking, timeout=timeout)

    def trigger(self, blocking: bool = True, timeout: Optional[float] = None):
        """Trigger the transition.

        Internally calls state machine's trigger().
        """
        # This method is a replaced by the state machine with the actual
        # implementation.

    def can_transition_from(self, from_state: State) -> bool:
        """Is transition possible from given state to target state."""
        return from_state in self.from_states

    def is_applicable(self, context: T) -> bool:
        """Can transition be applied right now.

        Returns True if transition is applicable. By default, returns
        value of is_applicable of the target state (to_sate) by default.
        """
        return self.to_state.is_applicable(context)


class GlobalTransition(Transition):
    """Global state transition.

    State transition from any state to given state.
    """

    def __init__(
        self,
        to_state: State,
        automatic: bool = False,
        name: Optional[str] = None,
        callback: Optional[Callable] = None,
    ):
        super().__init__(
            from_states=AnyState(),
            to_state=to_state,
            automatic=automatic,
            name=name,
            callback=callback,
        )
