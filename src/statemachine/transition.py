from typing import Callable
from typing import Generic
from typing import Optional

from . import T
from .state import AnyState
from .state import State


Callback_Type = Callable[[Optional[T]], None]


class Transition(Generic[T]):
    """State transition."""

    def __init__(
        self,
        from_states: State | list[State],
        to_state: State,
        automatic: bool = False,
        name: Optional[str] = None,
        callback: Optional[Callback_Type] = None,
    ):
        self.from_states = (
            from_states if isinstance(from_states, list) else [from_states]
        )
        self.to_state = to_state
        self.automatic = automatic
        self.name = name or ""
        self.callback = callback

        for state in self.from_states:
            if not isinstance(state, State):
                raise ValueError(f"Expecting State, got {state}.")

        if not isinstance(to_state, State):
            raise ValueError(f"Expecting State, got {to_state}.")

    def __str__(self):
        return f"{self.name} [auto]" if self.automatic else f"{self.name} [manual]"

    def __call__(self):
        self.trigger()

    def trigger(self):
        """Trigger the state transition."""
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
