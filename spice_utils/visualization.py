"""
Visualization configuration for Plotly and Bokeh.

Includes:
- Plotly and Bokeh theme configuration
- Observer sphere
- Observer and target annotations
- Multi-target 3D orbit visualization
"""

import numpy as np

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


# ============================================================
# Plot colors
# ============================================================

plt_clr = px.colors.qualitative.Prism


# ============================================================
# Plotly configuration
# ============================================================

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

    pio.templates.default = "plotly_dark+spice_dark"


# ============================================================
# Bokeh configuration
# ============================================================

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
# Observer sphere
# ============================================================

def sphere(radius, color="grey"):
    """
    Create a spherical Plotly surface centered at the origin.
    """

    theta = np.linspace(
        0,
        2 * np.pi,
        100,
    )

    phi = np.linspace(
        0,
        np.pi,
        100,
    )

    x = radius * np.outer(
        np.cos(theta),
        np.sin(phi),
    )

    y = radius * np.outer(
        np.sin(theta),
        np.sin(phi),
    )

    z = radius * np.outer(
        np.ones_like(theta),
        np.cos(phi),
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
        showlegend=False,
        name="Observer",
    )


# ============================================================
# Observer annotation
# ============================================================

def annot_obs(data):
    """
    Create an annotation identifying the observer.
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


# ============================================================
# Target annotations
# ============================================================

def annot_target(data, targetnum=0, color="teal"):
    """
    Create initial and final annotations for a target.

    Parameters
    ----------
    data : dict
        Shared trajectory data.

    targetnum : int
        Index of the target.

    color : str
        Annotation arrow color.

    Returns
    -------
    tuple
        Initial and final annotation dictionaries.
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
        "arrowcolor": color,
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
        "arrowcolor": color,
        "text": f"{target['name']} Final",
        "font": {
            "color": "antiquewhite",
            "size": 12,
        },
    }

    return initial, final


# ============================================================
# Target trajectory traces
# ============================================================

def add_target_traces(fig, target, color):
    """
    Add a target trajectory and its initial/final markers.

    All traces belonging to the target share a legend group.
    """

    x = np.asarray(target["rx"])
    y = np.asarray(target["ry"])
    z = np.asarray(target["rz"])

    name = target["name"]

    # --------------------------------------------------------
    # Trajectory
    # --------------------------------------------------------

    fig.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="lines",
            name=name,
            legendgroup=name,
            showlegend=True,
            line={
                "color": color,
                "width": 4,
            },
        )
    )

    # --------------------------------------------------------
    # Initial position
    # --------------------------------------------------------

    fig.add_trace(
        go.Scatter3d(
            x=[x[0]],
            y=[y[0]],
            z=[z[0]],
            mode="markers",
            name=f"{name} Initial",
            legendgroup=name,
            showlegend=False,
            marker={
                "color": color,
                "size": 5,
                "symbol": "circle",
            },
        )
    )

    # --------------------------------------------------------
    # Final position
    # --------------------------------------------------------

    fig.add_trace(
        go.Scatter3d(
            x=[x[-1]],
            y=[y[-1]],
            z=[z[-1]],
            mode="markers",
            name=f"{name} Final",
            legendgroup=name,
            showlegend=False,
            marker={
                "color": color,
                "size": 6,
                "symbol": "diamond",
            },
        )
    )


# ============================================================
# Multi-target orbit visualization
# ============================================================

def plot_orbit(data, targetnum=None):
    """
    Plot one or more target trajectories relative to the observer.

    Parameters
    ----------
    data : dict
        Shared trajectory data.

    targetnum : int or None, optional
        If None, plot all available targets.
        If an integer, plot only the selected target.

    Returns
    -------
    plotly.graph_objects.Figure
        Interactive 3D orbit visualization.
    """

    targets = data.get("target", [])

    if not targets:
        raise ValueError(
            "No target trajectories available."
        )

    # --------------------------------------------------------
    # Select targets
    # --------------------------------------------------------

    if targetnum is None:

        target_indices = list(
            range(len(targets))
        )

    else:

        if not 0 <= targetnum < len(targets):
            raise IndexError(
                f"Invalid target index: {targetnum}"
            )

        target_indices = [targetnum]

    # --------------------------------------------------------
    # Initialize figure
    # --------------------------------------------------------

    fig = go.Figure()

    annotations = [
        annot_obs(data)
    ]

    max_distance = 0.0

    # --------------------------------------------------------
    # Add each target
    # --------------------------------------------------------

    for index in target_indices:

        target = targets[index]

        color = plt_clr[
            index % len(plt_clr)
        ]

        x = np.asarray(target["rx"])
        y = np.asarray(target["ry"])
        z = np.asarray(target["rz"])

        if not (
            len(x) == len(y) == len(z)
        ) or len(x) == 0:
            raise ValueError(
                f"Invalid trajectory for {target['name']}."
            )

        # Add trajectory and markers
        add_target_traces(
            fig,
            target,
            color,
        )

        # Add target annotations
        annotations.extend(
            annot_target(
                data,
                targetnum=index,
                color=color,
            )
        )

        # Track maximum distance across all targets
        distances = np.sqrt(
            x**2 + y**2 + z**2
        )

        max_distance = max(
            max_distance,
            float(np.max(distances)),
        )

    # --------------------------------------------------------
    # Observer sphere
    # --------------------------------------------------------

    radius = 0.05 * max_distance

    if radius > 0:

        fig.add_trace(
            sphere(
                radius,
                color="grey",
            )
        )

    # --------------------------------------------------------
    # Layout
    # --------------------------------------------------------

    fig.update_layout(
        template="plotly_dark+spice_dark",

        title={
            "text": (
                "SPICE Trajectories Relative to "
                f"{data['observer']}"
            ),
            "x": 0.05,
        },

        margin={
            "l": 20,
            "r": 20,
            "b": 20,
            "t": 50,
        },

        width=700,
        height=650,

        showlegend=True,

        legend={
            "groupclick": "togglegroup",
        },

        scene={
            "annotations": annotations,
            "aspectmode": "data",

            "xaxis_title": "X (km)",
            "yaxis_title": "Y (km)",
            "zaxis_title": "Z (km)",
        },
    )

    # Preserve annotation information
    data["orbit_fig_annotations"] = annotations

    return fig