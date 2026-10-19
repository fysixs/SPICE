"""
polar_projection.py

Interactive 2D projection of SPICE trajectories.

Projects position vectors onto the XY plane of the
reference frame used for the ephemeris calculations.

Units:
    Position: km
    Time: SPICE ephemeris time (ET)
"""

import numpy as np

from bokeh.plotting import figure, show
from bokeh.layouts import column, row
from bokeh.models import (
    ColumnDataSource,
    CustomJS,
    Slider,
    Div,
    BasicTickFormatter,
    HoverTool,
)

from bokeh.palettes import Category10, Category20

from spice_utils.kinematics import calc_kinematics


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PLOT_SIZE = 650

PLOT_COLOR = "#667495"


def _target_colors(n):
    """
    Generate colors for multiple targets.
    """

    if n <= 10:
        palette = Category10[10]
    else:
        palette = Category20[20]

    return [
        palette[i % len(palette)]
        for i in range(n)
    ]


# --------------------------------------------------
# Projection calculations
# --------------------------------------------------

def calc_polar_kinematics(data):
    """
    Calculate 2D projected coordinates and polar
    quantities for each target.

    The projection uses the XY plane of the
    reference frame already used by SPICE.

    Modifies data in place.

    Parameters
    ----------
    data : dict
        SPICE analysis data.

    Returns
    -------
    dict
        Updated data dictionary.
    """

    calc_kinematics(data)

    for target in data["target"]:

        rx = np.asarray(target["rx"], dtype=float)
        ry = np.asarray(target["ry"], dtype=float)

        vx = np.asarray(target["vx"], dtype=float)
        vy = np.asarray(target["vy"], dtype=float)

        # Projected Cartesian coordinates
        x2d = rx
        y2d = ry

        # Projected radial distance
        rho = np.hypot(x2d, y2d)

        # Polar angle in projection plane
        theta = np.unwrap(
            np.arctan2(y2d, x2d)
        )

        # Signed angular velocity in XY plane
        omega = np.divide(
            x2d * vy - y2d * vx,
            rho**2,
            out=np.zeros_like(rho),
            where=rho > 0,
        )

        target.update({
            "x2D": x2d,
            "y2D": y2d,
            "rho2D": rho,
            "theta2D": theta,
            "omega2D": omega,
        })

    return data


# --------------------------------------------------
# Plot construction
# --------------------------------------------------

def plot_polar_orbit(
    source,
    current_source,
    target_names,
    colors,
    rmax,
):
    """
    Create interactive projected-orbit plot.
    """

    p = figure(
        width=PLOT_SIZE,
        height=PLOT_SIZE,
        x_range=(-rmax, rmax),
        y_range=(-rmax, rmax),
        title="2D Orbital Projection (XY Plane)",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        toolbar_location="above",
        match_aspect=True,
    )

    # Observer at origin
    p.scatter(
        x=[0],
        y=[0],
        marker="circle",
        size=20,
        line_color="#3288bd",
        fill_color="antiquewhite",
        line_width=2,
    )

    # Target trajectories
    for i, name in enumerate(target_names):

        p.line(
            x=f"x2D_{i}",
            y=f"y2D_{i}",
            source=source,
            line_color=colors[i],
            line_width=2,
            line_alpha=0.9,
            legend_label=name,
        )

        p.scatter(
            x=f"xnow_{i}",
            y=f"ynow_{i}",
            source=current_source,
            marker="circle_dot",
            size=14,
            line_color="red",
            fill_color=colors[i],
            fill_alpha=0.8,
        )

    p.xaxis.axis_label = "x (km)"
    p.yaxis.axis_label = "y (km)"

    p.axis.axis_label_text_font_size = "9pt"

    p.axis.formatter = BasicTickFormatter(
        power_limit_high=3,
        precision=1,
    )

    p.grid.visible = False

    # Legend
    p.legend.border_line_width = 2
    p.legend.border_line_color = PLOT_COLOR
    p.legend.border_line_alpha = 0.8

    p.legend.background_fill_color = PLOT_COLOR
    p.legend.background_fill_alpha = 0.2

    p.legend.click_policy = "hide"

    p.add_tools(
        HoverTool(
            tooltips=[
                ("Target", "$name"),
                ("x", "$x{0.000e} km"),
                ("y", "$y{0.000e} km"),
            ],
            mode="mouse",
        )
    )

    return p


# --------------------------------------------------
# Interactive interface
# --------------------------------------------------

def polar_projection(data):
    """
    Display an interactive 2D projection of
    all selected SPICE targets.

    The slider controls the displayed trajectory
    and current positions.
    """

    calc_polar_kinematics(data)

    targets = data["target"]

    n_targets = len(targets)

    if n_targets == 0:
        raise ValueError("No targets available.")

    n_steps = len(data["t"]["ET"])

    if n_steps < 2:
        raise ValueError(
            "At least two time samples are required."
        )

    names = [
        target["name"]
        for target in targets
    ]

    colors = _target_colors(n_targets)

    # ----------------------------------------------
    # Plot limits
    # ----------------------------------------------

    max_coordinate = max(
        np.max(
            np.abs(
                np.concatenate([
                    np.asarray(target["x2D"]),
                    np.asarray(target["y2D"]),
                ])
            )
        )
        for target in targets
    )

    rmax = 1.3 * max_coordinate

    if rmax <= 0:
        rmax = 1.0

    # ----------------------------------------------
    # Widgets
    # ----------------------------------------------

    observer = Div(
        text=f"<b>Observer:</b> {data['observer']}",
        width=250,
    )

    time_display = Div(
        text=f"<b>Date:</b> {data['t']['UTC'][0]}",
        width=350,
    )

    time_slider = Slider(
        start=0,
        end=n_steps - 1,
        value=0,
        step=1,
        title="Time Step:",
        width=600,
    )

    # ----------------------------------------------
    # Full trajectory data
    # ----------------------------------------------

    full_data = {}

    for i, target in enumerate(targets):

        full_data[f"x2D_{i}"] = (
            np.asarray(target["x2D"]).tolist()
        )

        full_data[f"y2D_{i}"] = (
            np.asarray(target["y2D"]).tolist()
        )

    # ----------------------------------------------
    # Initial trajectory data
    # ----------------------------------------------

    initial_data = {}

    current_data = {}

    for i, target in enumerate(targets):

        x = float(target["x2D"][0])
        y = float(target["y2D"][0])

        initial_data[f"x2D_{i}"] = [x]
        initial_data[f"y2D_{i}"] = [y]

        current_data[f"xnow_{i}"] = [x]
        current_data[f"ynow_{i}"] = [y]

    source = ColumnDataSource(
        data=initial_data
    )

    current_source = ColumnDataSource(
        data=current_data
    )

    # ----------------------------------------------
    # Create plot
    # ----------------------------------------------

    orbit_plot = plot_polar_orbit(
        source=source,
        current_source=current_source,
        target_names=names,
        colors=colors,
        rmax=rmax,
    )

    # ----------------------------------------------
    # JavaScript callback
    # ----------------------------------------------

    callback = CustomJS(
        args={
            "source": source,
            "current_source": current_source,
            "full_data": full_data,
            "n_targets": n_targets,
            "time_display": time_display,
            "dates": [str(t) for t in data["t"]["UTC"]],
        },
        code="""
            const idx = cb_obj.value;

            const trajectory = {};
            const current = {};

            for (let i = 0; i < n_targets; i++) {

                const x = full_data[`x2D_${i}`];
                const y = full_data[`y2D_${i}`];

                trajectory[`x2D_${i}`] =
                    x.slice(0, idx + 1);

                trajectory[`y2D_${i}`] =
                    y.slice(0, idx + 1);

                current[`xnow_${i}`] = [x[idx]];
                current[`ynow_${i}`] = [y[idx]];
            }

            source.data = trajectory;
            current_source.data = current;

            time_display.text =
                `<b>Date:</b> ${dates[idx]}`;
        """,
    )

    time_slider.js_on_change(
        "value",
        callback,
    )

    # ----------------------------------------------
    # Interface
    # ----------------------------------------------

    interface = column(
        row(observer, time_display),
        orbit_plot,
        time_slider,
    )

    show(interface)

    return interface