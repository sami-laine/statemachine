import typing
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorInfo:
    """Error info.

    ErrorInfo is passed to StateMachine.on_error() handler.
    """

    error: type
    value: str
    traceback: str


class StateMachineError(Exception):
    """Generic base for state machine errors."""


class ConfigurationError(StateMachineError):
    """Configuration error.

    Raised for example if initial state is not used.
    """


class AlreadyStartedError(StateMachineError):
    """State machine is already started."""


class NotAliveError(StateMachineError):
    """State machine is not alive.

    Raised if state machine is not alive, although it would need to be
    to execute the requested method.
    """


class Halted(StateMachineError):
    """State machine is halted.

    Raised is a user tries to trigger a state transition but
    the state machine is halted due an error.
    """


class InvalidTransitionError(StateMachineError):
    """Raised if a state transition in not applicable."""


class TransitionError(StateMachineError):
    """Raised if an error occurs while triggering transition.

    Raised if error occurs while executing `on_trigger()` of
    a Transition instance.
    """


class StateMachineBusyError(TransitionError):
    """Raised when a transition cannot proceed because the state machine is in use."""


class NoTransitionAvailable(StateMachineError):
    """Raised if not transition is available."""


class StateError(StateMachineError):
    """Raised if an error occurs while applying a state.

    Raised if an error occurs while calling `on_entry()` or `on_exit()`.
    """


class FinalStateReached(StateMachineError):
    """Raised when final state is reached."""
