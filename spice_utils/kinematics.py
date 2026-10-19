"""
kinematics.py

Kinematic calculations and interactive visualization
for SPICE-generated position and velocity data.

Units:
    Position:     km
    Velocity:     km/s
    Acceleration: km/s^2
"""

import numpy as np

from bokeh.plotting import figure, show
from bokeh.layouts import column, row
from bokeh.models import (
    ColumnDataSource,
    CustomJS,
    Select,
    Div,
    HoverTool,
    BasicTickFormatter,
    TabPanel,
    Tabs,
)


# --------------------------------------------------
# Plot configuration
# --------------------------------------------------

PLOT_COLORS = [
    "#667495",
    "#D98C5F",
    "#78A69A",
    "#735D9D",
]

PLOT_WIDTH = 600
PLOT_HEIGHT = 400


# --------------------------------------------------
# Kinematic calculations
# --------------------------------------------------

def calc_kinematics(data):
    """
    Calculate position, velocity, and acceleration
    magnitudes and components for every target.

    Modifies the supplied data dictionary in place.

    Parameters
    ----------
    data : dict
        SPICE analysis data containing:

        data["t"]["ET"]
        data["target"]

    Returns
    -------
    dict
        Updated data dictionary.
    """

    et = np.asarray(data["t"]["ET"], dtype=float)

    if len(et) < 2:
        raise ValueError(
            "At least two time samples are required "
            "to calculate acceleration."
        )

    if not np.all(np.diff(et) > 0):
        raise ValueError(
            "Ephemeris times must be strictly increasing."
        )

    for target in data["target"]:

        # Position components
        rx = np.asarray(target["rx"], dtype=float)
        ry = np.asarray(target["ry"], dtype=float)
        rz = np.asarray(target["rz"], dtype=float)

        # Velocity components
        vx = np.asarray(target["vx"], dtype=float)
        vy = np.asarray(target["vy"], dtype=float)
        vz = np.asarray(target["vz"], dtype=float)

        # Vector magnitudes
        r = np.sqrt(rx**2 + ry**2 + rz**2)
        v = np.sqrt(vx**2 + vy**2 + vz**2)

        # Acceleration components
        edge_order = 2 if len(et) >= 3 else 1

        ax = np.gradient(vx, et, edge_order=edge_order)
        ay = np.gradient(vy, et, edge_order=edge_order)
        az = np.gradient(vz, et, edge_order=edge_order)

        # Acceleration vector magnitude
        a = np.sqrt(ax**2 + ay**2 + az**2)

        target.update({
            "r": r,
            "v": v,
            "ax": ax,
            "ay": ay,
            "az": az,
            "a": a,
        })

    return data


# --------------------------------------------------
# Bokeh plot helpers
# --------------------------------------------------

def _create_figure(title, ylabel):
    """
    Create a consistently formatted Bokeh figure.
    """

    p = figure(
        width=PLOT_WIDTH,
        height=PLOT_HEIGHT,
        title=title,
        tools="pan,wheel_zoom,box_zoom,reset,save,hover",
        toolbar_location="above",
        x_axis_type="datetime",
    )

    p.xaxis.axis_label = "Time"
    p.yaxis.axis_label = ylabel

    p.axis.axis_label_text_font_size = "9pt"

    p.yaxis.formatter = BasicTickFormatter(
        power_limit_high=3,
        precision=1,
    )

    return p


def plot_magnitude(variable, title, ylabel, source):
    """
    Plot the magnitude of a kinematic quantity.
    """

    p = _create_figure(title, ylabel)

    p.line(
        x="t",
        y=variable,
        source=source,
        line_color=PLOT_COLORS[3],
        line_width=2,
        line_alpha=0.9,
    )

    hover = p.select_one(HoverTool)

    hover.tooltips = [
        ("Date", "@t{%F}"),
        (ylabel, f"@{{{variable}}}{{%0.3e}}"),
    ]

    hover.formatters = {
        "@t": "datetime",
        f"@{{{variable}}}": "printf",
    }

    return p


def plot_components(variable, title, ylabel, source):
    """
    Plot x, y, and z components of a vector.
    """

    p = _create_figure(title, ylabel)

    components = ["x", "y", "z"]

    for i, component in enumerate(components):

        field = f"{variable}{component}"

        p.line(
            x="t",
            y=field,
            source=source,
            line_color=PLOT_COLORS[i],
            line_width=2,
            line_alpha=0.9,
            legend_label=field,
        )

    # Legend styling
    p.legend.border_line_width = 2
    p.legend.border_line_color = "#667495"
    p.legend.border_line_alpha = 0.8

    p.legend.background_fill_color = "#667495"
    p.legend.background_fill_alpha = 0.2

    p.legend.click_policy = "hide"

    # Hover information
    hover = p.select_one(HoverTool)

    hover.tooltips = [
        ("Date", "@t{%F}"),
        (
            f"{variable}x",
            f"@{{{variable}x}}{{%0.3e}}",
        ),
        (
            f"{variable}y",
            f"@{{{variable}y}}{{%0.3e}}",
        ),
        (
            f"{variable}z",
            f"@{{{variable}z}}{{%0.3e}}",
        ),
    ]

    hover.formatters = {
        "@t": "datetime",
        f"@{{{variable}x}}": "printf",
        f"@{{{variable}y}}": "printf",
        f"@{{{variable}z}}": "printf",
    }

    return p


# --------------------------------------------------
# Data source preparation
# --------------------------------------------------

def _target_source(data, target_index):
    """
    Build a Bokeh-compatible data dictionary
    for one target.
    """

    target = data["target"][target_index]

    fields = [
        "rx", "ry", "rz", "r",
        "vx", "vy", "vz", "v",
        "ax", "ay", "az", "a",
    ]

    result = {
        "t": list(data["t"]["UTC"]),
    }

    for field in fields:
        result[field] = np.asarray(
            target[field]
        ).tolist()

    return result


# --------------------------------------------------
# Interactive kinematics interface
# --------------------------------------------------

def kinplots(data):
    """
    Display interactive kinematic plots.

    Includes:
        Position components and magnitude
        Velocity components and magnitude
        Acceleration components and magnitude

    Parameters
    ----------
    data : dict
        SPICE analysis data.
    """

    # Calculate kinematic quantities
    calc_kinematics(data)

    targets = data["target"]

    if not targets:
        raise ValueError("No targets available.")

    target_names = [
        target["name"]
        for target in targets
    ]

    # ----------------------------------------------
    # Widgets
    # ----------------------------------------------

    target_selection = Select(
        title="Target:",
        value=target_names[0],
        options=target_names,
        width=200,
    )

    observer = Div(
        text=f"<b>Observer:</b> {data['observer']}",
        width=250,
    )

    # ----------------------------------------------
    # Data sources
    # ----------------------------------------------

    source = ColumnDataSource(
        data=_target_source(data, 0)
    )

    all_targets = [
        _target_source(data, i)
        for i in range(len(targets))
    ]

    # ----------------------------------------------
    # Target selection callback
    # ----------------------------------------------

    callback = CustomJS(
        args={
            "source": source,
            "all_targets": all_targets,
            "target_names": target_names,
        },
        code="""
            const index = target_names.indexOf(cb_obj.value);

            if (index < 0) {
                return;
            }

            const selected = all_targets[index];

            source.data = {...selected};

            source.change.emit();
        """,
    )

    target_selection.js_on_change(
        "value",
        callback,
    )

    # ----------------------------------------------
    # Position plots
    # ----------------------------------------------

    posplot = plot_components(
        "r",
        "Orbital Position Components",
        "Position (km)",
        source,
    )

    distplot = plot_magnitude(
        "r",
        "Orbital Distance",
        "Distance (km)",
        source,
    )

    # ----------------------------------------------
    # Velocity plots
    # ----------------------------------------------

    velplot = plot_components(
        "v",
        "Orbital Velocity Components",
        "Velocity (km/s)",
        source,
    )

    speedplot = plot_magnitude(
        "v",
        "Orbital Speed",
        "Speed (km/s)",
        source,
    )

    # ----------------------------------------------
    # Acceleration plots
    # ----------------------------------------------

    accplot = plot_components(
        "a",
        "Orbital Acceleration Components",
        "Acceleration (km/s²)",
        source,
    )

    accmagplot = plot_magnitude(
        "a",
        "Orbital Acceleration Magnitude",
        "Acceleration (km/s²)",
        source,
    )

    # ----------------------------------------------
    # Tabs
    # ----------------------------------------------

    tab_position = TabPanel(
        child=row(posplot, distplot),
        title="Position",
    )

    tab_velocity = TabPanel(
        child=row(velplot, speedplot),
        title="Velocity",
    )

    tab_acceleration = TabPanel(
        child=row(accplot, accmagplot),
        title="Acceleration",
    )

    tabs = Tabs(
        tabs=[
            tab_position,
            tab_velocity,
            tab_acceleration,
        ],
        tabs_location="left",
    )

    # ----------------------------------------------
    # Interface
    # ----------------------------------------------

    interface = column(
        row(target_selection, observer),
        tabs,
    )

    show(interface)

    return interface