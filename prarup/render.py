"""Render a Document into LaTeX for a target conference.

Pure: builds a string from data. Nothing here writes a file or runs a
program.
"""

from pathlib import Path

import jinja2

from prarup.models import Document

TEMPLATES = Path(__file__).parent / "templates"


def _environment() -> jinja2.Environment:
    """Jinja2 configured so its syntax does not collide with LaTeX.

    The default {{ }} and {% %} clash badly with LaTeX braces, and the
    templates become both unreadable and ambiguous. \\VAR{} and \\BLOCK{}
    look like LaTeX commands, so a template still reads as LaTeX.

    autoescape stays off. Jinja2's escaping is HTML-shaped and would
    corrupt every backslash in the output.
    """
    return jinja2.Environment(
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        keep_trailing_newline=True,
        loader=jinja2.FileSystemLoader(TEMPLATES),
    )


def render(document: Document, template: str = "ieee") -> str:
    """Return the LaTeX source for this document in the given template."""
    env = _environment()
    return env.get_template(f"{template}.tex.j2").render(doc=document)
