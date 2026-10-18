"""
Visualization configuration for Plotly and Bokeh.
"""

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from bokeh.io import output_notebook, curdoc
from bokeh.themes import Theme

from .config import (
    ui_clr,
    BACKGROUND,
    PLOT_BACKGROUND,
    TEXT_COLOR,
    GRID_COLOR,
)


# Plot colors
plt_clr = px.colors.qualitative.Prism


def configure_plotly():
    """
    Configure the default Plotly renderer and custom dark theme.
    """

    pio.renderers.default = "colab"

    theme = go.layout.Template(
        layout={
            "paper_bgcolor": PLOT_BACKGROUND,
            "plot_bgcolor": BACKGROUND,
            "font": {
                "color": TEXT_COLOR,
            },
            "colorway": plt_clr,

            "hovermode": "closest",

            "hoverlabel": {
                "align": "left",
            },

            "title": {
                "x": 0.05,
            },

            "xaxis": {
                "automargin": True,
                "gridcolor": "#283442",
                "linecolor": GRID_COLOR,
                "zerolinecolor": "#283442",
                "zerolinewidth": 2,
                "title": {
                    "standoff": 15,
                },
            },

            "yaxis": {
                "automargin": True,
                "gridcolor": "#283442",
                "linecolor": GRID_COLOR,
                "zerolinecolor": "#283442",
                "zerolinewidth": 2,
                "title": {
                    "standoff": 15,
                },
            },

            "scene": {
                axis: {
                    "backgroundcolor": BACKGROUND,
                    "gridcolor": GRID_COLOR,
                    "gridwidth": 2,
                    "linecolor": GRID_COLOR,
                    "showbackground": False,
                    "showgrid": False,
                    "showline": True,
                    "ticks": "outside",
                    "zeroline": False,
                }
                for axis in ("xaxis", "yaxis", "zaxis")
            },

            "legend": {
                "bgcolor": PLOT_BACKGROUND,
                "font": {
                    "color": TEXT_COLOR,
                },
            },

            "coloraxis": {
                "colorbar": {
                    "outlinewidth": 0,
                },
            },
        }
    )

    pio.templates["spice_dark"] = theme

    # Inherit remaining settings from Plotly's dark template
    pio.templates.default = "plotly_dark+spice_dark"


def configure_bokeh():
    """
    Initialize Bokeh and apply the SPICE dark theme.
    """

    output_notebook()

    theme = Theme(
        json={
            "attrs": {
                "figure": {
                    "background_fill_color": PLOT_BACKGROUND,
                    "border_fill_color": BACKGROUND,
                    "outline_line_color": TEXT_COLOR,
                    "outline_line_alpha": 0.25,
                },

                "Grid": {
                    "grid_line_color": TEXT_COLOR,
                    "grid_line_alpha": 0.25,
                },

                "Axis": {
                    "major_tick_line_alpha": 0.8,
                    "major_tick_line_color": "lightgrey",

                    "minor_tick_line_alpha": 0.8,
                    "minor_tick_line_color": "lightgrey",

                    "axis_line_alpha": 0.8,
                    "axis_line_color": ui_clr["slider"],

                    "major_label_text_color": "lightgrey",
                    "major_label_text_font": "Helvetica",
                    "major_label_text_font_size": "8pt",

                    "axis_label_standoff": 10,
                    "axis_label_text_color": TEXT_COLOR,
                    "axis_label_text_font": "Helvetica",
                    "axis_label_text_font_size": "1.25em",
                    "axis_label_text_font_style": "normal",
                },

                "Legend": {
                    "spacing": 8,
                    "glyph_width": 15,

                    "label_standoff": 8,
                    "label_text_color": TEXT_COLOR,
                    "label_text_font": "Helvetica",
                    "label_text_font_size": "1.025em",

                    "border_line_alpha": 0,
                    "background_fill_alpha": 0.25,
                    "background_fill_color": PLOT_BACKGROUND,
                },

                "ColorBar": {
                    "title_text_color": TEXT_COLOR,
                    "title_text_font": "Helvetica",
                    "title_text_font_size": "1.025em",
                    "title_text_font_style": "normal",

                    "major_label_text_color": TEXT_COLOR,
                    "major_label_text_font": "Helvetica",
                    "major_label_text_font_size": "1.025em",

                    "background_fill_color": BACKGROUND,
                    "major_tick_line_alpha": 0,
                    "bar_line_alpha": 0,
                },

                "Title": {
                    "text_color": TEXT_COLOR,
                    "text_font": "Helvetica",
                    "text_font_size": "1.15em",
                },
            }
        }
    )

    curdoc().theme = theme

    return theme

# ============================================================
# Orbit visualization
# ============================================================

import numpy as np


def sphere(radius, color="grey"):
    """
    Create a spherical Plotly surface centered at the origin.
    """

    theta = np.linspace(
        0,
        2 * np.pi,
        100
    )

    phi = np.linspace(
        0,
        np.pi,
        100
    )

    x = radius * np.outer(
        np.cos(theta),
        np.sin(phi)
    )

    y = radius * np.outer(
        np.sin(theta),
        np.sin(phi)
    )

    z = radius * np.outer(
        np.ones_like(theta),
        np.cos(phi)
    )

    return go.Surface(
        x=x,
        y=y,
        z=z,
        colorscale=[
            [0, color],
            [1, color],
        ],
        showscale=False,
        hoverinfo="skip",
    )


def annot_obs(data):
    """
    Create the observer annotation.
    """

    return {
        "showarrow": False,
        "x": 0,
        "y": 0,
        "z": 0,
        "xshift": 20,
        "text": data["observer"],
        "xanchor": "left",
        "font": {
            "color": "antiquewhite",
            "size": 12,
        },
    }


def annot_target(data, targetnum=0):
    """
    Create initial and final target annotations.
    """

    target = data["target"][targetnum]

    initial = {
        "showarrow": True,
        "x": target["rx"][0],
        "y": target["ry"][0],
        "z": target["rz"][0],
        "ax": 0,
        "ay": -50,
        "arrowhead": 3,
        "yshift": 10,
        "arrowcolor": "teal",
        "text": f"{target['name']} Initial",
        "font": {
            "color": "antiquewhite",
            "size": 12,
        },
    }

    final = {
        "showarrow": True,
        "x": target["rx"][-1],
        "y": target["ry"][-1],
        "z": target["rz"][-1],
        "ax": 0,
        "ay": -50,
        "arrowhead": 3,
        "yshift": 10,
        "arrowcolor": "teal",
        "text": f"{target['name']} Final",
        "font": {
            "color": "antiquewhite",
            "size": 12,
        },
    }

    return initial, final


def plot_orbit(data, targetnum=0):
    """
    Plot the selected target's trajectory relative
    to the observer.
    """

    target = data["target"][targetnum]

    x = target["rx"]
    y = target["ry"]
    z = target["rz"]

    fig = go.Figure()

    # Orbit trajectory
    fig.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="lines",
            name=target["name"],
        )
    )

    # Initial position
    fig.add_trace(
        go.Scatter3d(
            x=[x[0]],
            y=[y[0]],
            z=[z[0]],
            mode="markers",
            marker={
                "color": "green",
                "size": 5,
            },
            name="Initial",
        )
    )

    # Final position
    fig.add_trace(
        go.Scatter3d(
            x=[x[-1]],
            y=[y[-1]],
            z=[z[-1]],
            mode="markers",
            marker={
                "color": "red",
                "size": 5,
            },
            name="Final",
        )
    )

    # Observer sphere
    distances = np.sqrt(
        x**2 + y**2 + z**2
    )

    radius = 0.05 * np.max(distances)

    if radius > 0:
        fig.add_trace(
            sphere(radius, "grey")
        )

    annotations = [
        annot_obs(data),
        *annot_target(data, targetnum),
    ]

    fig.update_layout(
        template="spice_dark",
        margin={
            "l": 20,
            "r": 20,
            "b": 20,
            "t": 20,
        },
        width=600,
        showlegend=False,
        scene={
            "annotations": annotations,
            "aspectmode": "data",
        },
    )

    data["orbit_fig_annotations"] = annotations

    return fig