# Python State Machine Module

This module provides a simple and flexible implementation of a **finite state machine**. It allows you to define **states**, **transitions**, and context-aware logic using a clean, 
object-oriented API.

It supports manual and automatic transitions, initial and final states, error handling
and callbacks for state changes.


# ✨ Features

* State and transition definitions
* Manual and automatic transitions
* Context-aware state logic
* Entry/exit hooks for each state
* Error handling and recovery
* Thread-safe execution


# 📦 Installation

```bash
pip install -e .
```

# 🚀 Quick Start

Here’s a minimal example to illustrate how a state machine works:

```python
from statemachine import StateMachine, State, FinalState

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()
        
        # Define states
        a = State()
        b = State()
        c = FinalState()
            
        # Define transitions
        self.a_to_b = self.connect(a, b)      # manual transition
        self.connect(b, c, automatic=True)    # automatic transition

        # Set initial state
        self.initial_state = a
        
# Instantiate and start the machine
sm = ExampleMachine()
sm.start()

# Trigger the manual transition from a → b
sm.a_to_b()

# Wait until the machine reaches the final state
sm.join()
```

* `start()` launches the machine on a background thread.
* Manual transitions are invoked by calling the transition (`sm.a_to_b()`).
* Automatic transitions fire as soon as the source state becomes active.
* `join()` blocks until a final state is reached (or `stop()` is called).


# 🧩 Defining States

States can be created simply instantiating `State`.

```Python
from statemachine import StateMachine, State

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()
        
        a = State()
        b = State()
        c = State()
```

## Initial State

Define initial state by using `initial_state`. State machine is expected to have exactly one initial state.
`InitialStateNotSetError` is raised if not set.

```Python
from statemachine import StateMachine, State

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()
        
        a = State()
        b = State()
        
        # Set initial state
        self.initial_state = a
```

## Final State

A final state signals completion and stops the machine automatically. You can declare 
one or more final states:

```python
from statemachine import StateMachine, State, FinalState

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()
        
        a = State()
        b = State()
        c = FinalState()
```

Alternatively, you can raise the `FinalStateReached` exception inside a state hook.


## Subclassing State

Each state in your machine can implement three hooks:

```python
from statemachine import State, T

class MyState(State[T]):
    def is_applicable(self, context: T) -> bool:
        """Return True if this state can be entered in the current context."""
        return True

    def on_entry(self, context: T):
        """Called when entering this state."""
        ...

    def on_exit(self, context: T):
        """Called when exiting this state."""
        ...
```

* `is_applicable(context)` Decide at runtime whether this state is eligible to be entered.
* `on_entry(context)` Execute state specific logic when the state is activated.
* `on_exit(context)` Clean up or cancel pending operations when leaving the state.


# 🔁 Transitions

Transitions govern the movement between states. You can define the state transitions by using `connect()`.

```python
from statemachine import StateMachine, State, FinalState

class ExampleMachine(StateMachine[T]):
    def __init__(self):
        super().__init__()
    
        a = State()
        b = State()
        c = FinalState()
        
        # Manual transition from a → b
        transition = self.connect(a, b)
        
        # Automatic transition from b → c
        self.connect(b, c, automatic=True)
```

`connect()` returns `Transition` object. Transition object encapsulates the transition details and can be called 
like any other callable. This makes it possible to use the transition objects like methods.

Internally `Transition` calls `trigger()`. 


## Triggering

```python
sm = ExampleMachine()
sm.start()
sm.transition()
```

or 

```python
sm.transition.trigger()
```

* Manual: Call the transition `transition()` like any callable.
* Automatic: Automatic transitions fire as soon as the source state becomes active.

However, sometimes it might make sense to expose the transition objects via normal methods.

```python
from statemachine import StateMachine, State, FinalState

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()        
        
        a = State()
        b = State()
        c = FinalState()

        self._transition = self.connect(a, b)

    def a_to_b(self):
        self._transition.trigger()
```

This gives also a change to add additional logic before and after triggering the transition. However, it is good 
to consider if the logic needs to be thread safe.

It is also possible to overwrite stub methods like this:

```python
from statemachine import StateMachine, State, FinalState

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()        
        
        a = State()
        b = State()
        c = FinalState()

        self.a_to_b = self.connect(a, b)

    def a_to_b(self): pass
```

This helps for example **PyCharm**'s autocompletion to detect `a_to_b()` as a **method** - not as an **attribute**. This is 
due how **PyCharm** analyses Python class signatures. 


## Multi-Source Transitions

One transition can originate from several states:

```python

from statemachine import StateMachine, State

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()
        
        a = State()
        b = State()
        c = State()
        
        self.reset = self.connect([a, b, c], a)
```

## Global Transitions

Global transition can originate from any state.

```python
from statemachine import StateMachine, State

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()
        
        a = State()
        b = State()
        c = State()
    
        self.reset = self.add_global_transition(a)
```


## ⌗ Context Object

Pass a context object into your machine to carry data through transitions:

```python
from dataclasses import dataclass
from statemachine import StateMachine, State, FinalState

@dataclass
class Context:
    value: int = 0

class StateA(State[Context]):
    def on_entry(self, ctx: Context):
        ctx.value += 1

class ExampleMachine(StateMachine[Context]):
    def __init__(self, context: Context):
        super().__init__(context)
        
        a = StateA()
        b = State()
        c = FinalState()
        
        # Manual transition from a → b
        self.a_to_b = self.connect(a, b)
        
        # Automatic transition from b → c
        self.connect(b, c, automatic=True)        
        
        # Set initial state
        self.initial_state = a

sm = ExampleMachine(Context())
sm.start()
sm.a_to_b()
sm.join()

print(sm.context.value)  # => 1
```

The context can hold configuration, device handles, counters, or any runtime
data your states need.


# 💥 Error Handling

When a state’s hook raises an error, the machine enters a **halted** state. Define
`handle_error()` to recover:

```python
from typing import Optional
from statemachine import StateMachine, State, ErrorInfo, T


class ExampleStateMachine(StateMachine):

    def handle_error(self, error_info: ErrorInfo) -> Optional[State]:
        # Inspect error
        print(f"Error in {self.state}: {error_info.error.__name__}")

        # Resolve error
        # ...

        # Resume execution
        self.resume()

        # Optionally return a state to redirect the flow
        return self.initial_state
```

* The machine halts until you call `resume()`.
* Return a state to redirect the next transition, or return `None` to continue normally.
* If recovery isn’t possible, you can log the error and leave the machine halted or stop it.


# 🔔 Callbacks

Beyond `on_entry`/`on_exit`, the machine itself provides a few hooks:

* `on_start()` Invoked when `start()` is called.
* `on_state_changed(from_state, to_state)` Triggered after every successful transition.
* `on_state_applied(state)` Called after state machine has fully applied a state. This includes calling state's `on_entry()`. 
* `on_exit()` Called when the machine stops (via `stop()`, final state, or unhandled error).

Override these methods to integrate with your application’s logging, UI updates, or metrics.


# 🖼️ Visualization

## State Diagram

You can how a state diagram by calling `show_state_diagram()`.
It uses a default web browser to render and open the state diagram:

```python
from statemachine import StateMachine, State, FinalState
from statemachine.diagram import show_state_diagram

class ExampleMachine(StateMachine):
    def __init__(self):
        super().__init__()        
        
        a = State()
        b = State()
        c = FinalState()

        # Manual transition from a → b
        self.a_to_b = self.connect(a, b)
        
        # Automatic transition from b → c
        self.connect(b, c, automatic=True)        
        
        # Set initial state
        self.initial_state = a
        
    def a_to_b(self): pass
        
sm = ExampleMachine()

# Shows state machine state diagram on default web browser.
show_state_diagram(sm)
```

# Development

## Create virtual environment

```shell
python3 -m venv venv
```

## Activate virtual environment

```shell
source venv/bin/activate
```

## Install in "editable" mode

```bash
pip install -e .
```

## Generating distribution archive

```shell
python3 -m pip install --upgrade build
python3 -m build
```


# 🧪 Running Tests

This project uses pytest. 

## Installation

If you don’t have pytest installed yet, you can add it to your development environment:

```bash
pip install pytest
```
## Running Tests With Pytest

To run all tests in the project, simply execute:

```bash
pytest
```

This will automatically discover and run all test files named `test_*.py` or 
`*_test.py` in the project directory.

You can run a specific test file:

```bash
pytest tests/test_transitions.py::test_state
```

Tips:

* Use `-v` for verbose output: `pytest -v`
* Use `-s` to output print statements.
* Use `--maxfail=1` to stop after the first failure
* Use `--tb=short` for shorter tracebacks


# 📝 License

This project is licensed under the **MIT License**.

_**Copyright 2025 Sami Laine.**_

_Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the “Software”), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:_

_**The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.**_
