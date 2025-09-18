import logging
import textwrap
import time
import webbrowser
from string import Template
from tempfile import NamedTemporaryFile
from typing import Optional

from statemachine import FinalState
from statemachine import StateMachine

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({ startOnLoad: true });
  </script>
</head>
<body>
  <div class="mermaid">
    ---
    title: $name
    ---
    stateDiagram-v2
$diagram
  </div>
</body>
</html>
"""


def show_state_diagram(state_machine: StateMachine, name: Optional[str] = None):
    """Render and open state diagram on a web browser.

    Creates a state diagram of the provided state machine, wraps the
    diagram as a HTML page and opens it with the default web browser.
    """
    name = state_machine.__class__.__name__ if name is None else name

    logger.debug("Create state diagram: %s", name)

    # Create text based state diagram.
    state_diagram = create_state_diagram(state_machine)
    logger.debug(state_diagram)

    # Create HTML page with embedded state diagram.
    html = _create_html_page_with_state_diagram(name, state_diagram)

    # Write the HTML page into a temporary HTML file to be opened with
    # a default web browser.
    _open_with_web_browser(html)


def create_state_diagram(state_machine: StateMachine) -> str:
    """Create a text based representation of the given state machine.

    This implementation uses Mermaid to render the state diagram.
    Mermaid documentation sais it "The syntax tries to be compliant with
    the syntax used in plantUml as this will make it easier for users to
    share diagrams between mermaid and plantUml."

    See also https://mermaid.js.org/syntax/stateDiagram.html.
    """
    initial_state = state_machine.initial_state
    state_names_by_ids: dict[str, str] = {}
    transitions = []

    for t in state_machine.transitions():
        to_state_id = _get_id(t.to_state.name)

        for from_state in t.from_states:
            if from_state is initial_state:
                line = f"[*] --> "
            else:
                from_state_id = _get_id(from_state.name)
                state_names_by_ids[from_state_id] = from_state.name
                line = f"{from_state_id} --> "

            if isinstance(t.to_state, FinalState):
                line += "[*]"
            else:
                state_names_by_ids[to_state_id] = t.to_state.name
                line += f"{to_state_id}"

            if t.name or t.automatic:
                line += " : "

            if t.name:
                line += t.name

            if t.automatic:
                line += " [auto]"

            transitions.append(line)

    state_definitions = [f"{id}: {name}" for id, name in state_names_by_ids.items()]
    return "\n".join(state_definitions + [""] + transitions)


def _get_id(name: str) -> str:
    """Get state id."""
    return name.replace(" ", "_").lower()


def _create_html_page_with_state_diagram(
    name: str, diagram: str, template: str = HTML_TEMPLATE
):
    """Create a HTML page with given state diagram."""
    indented_text = textwrap.indent(diagram, " " * 6)
    return Template(template).safe_substitute(name=name, diagram=indented_text)


def _open_with_web_browser(content: str, suffix: str = ".html", delete: bool = True):
    """Write content to a temp file and open it with default web browser.

    Creates a temporary HTML file. Writes the given HTML content into the file
    and open the temporary file with web browser.

    The temporary file gets deleted by default. Use `delete=False` to preserve the file.
    """
    with NamedTemporaryFile(
        delete=delete, suffix=suffix, mode="w", encoding="utf-8"
    ) as fh:
        fh.write(content)
        fh.flush()

        logger.debug("State diagram written to %s.", fh.name)

        _open_web_page(fh.name)

        # We give some time to the web browser to render the page before
        # exiting the context and the temporary file gets deleted.
        time.sleep(3.0 if delete else 0.0)


def _open_web_page(filename: str):
    """Open a file on a web browser."""
    webbrowser.open(f"file:///{filename}")
