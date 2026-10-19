"""
SPICE notebook environment initialization.
"""

from IPython.display import display, Markdown

from .visualization import (
    configure_plotly,
    configure_bokeh,
)


def initialize_environment():
    """
    Initialize visualization settings for the notebook.
    """

    configure_plotly()

    bokeh_theme = configure_bokeh()

    display(
        Markdown(
            "<font size=3> **Environment Setup Complete!** "
            
            "<font size=3> Please run the next cell to select a mission."
        )
    )

    return bokeh_theme