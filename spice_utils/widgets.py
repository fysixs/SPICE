"""
Interactive notebook widgets for SPICE mission selection.
"""

import datetime

import ipywidgets as widgets
from pathlib import Path

from IPython.display import (
    display,
    Markdown
)

from .config import ui_clr
from .kernels import setup_naif_mission
from .kernels import get_available_naif_ids
from .geometry import get_data
from .visualization import plot_orbit


def import_data(spiceDf):
    """
    Create the mission selection and download interface.

    Parameters
    ----------
    spiceDf : pandas.DataFrame
        NAIF archived mission catalog.

    Returns
    -------
    dict
        Widget references and selected mission data.
    """

    required_columns = {
        "Mission Name",
        "Start Time",
        "Stop Time",
        "Subset Link",
        "Archive Readme",
    }

    missing = (
        required_columns - set(spiceDf.columns)
    )

    if missing:
        raise ValueError(
            f"Missing catalog columns: {sorted(missing)}"
        )

    if spiceDf.empty:
        raise ValueError(
            "Mission catalog is empty."
        )

    # Use positional indexing consistently.
    missions = spiceDf.reset_index(drop=True)

    mission_list = [
        (name, index)
        for index, name in enumerate(
            missions["Mission Name"]
        )
    ]

    mission_select = widgets.Dropdown(
        options=mission_list,
        value=0,
        description="Mission:",
        layout=widgets.Layout(
            width="auto",
        ),
    )

    def mission_date(field):
        """
        Return the selected mission's date.
        """

        value = missions.iloc[
            mission_select.value
        ][field]

        return datetime.date.fromisoformat(
            str(value).strip()
        )

    startDate = widgets.DatePicker(
        description="Start Date:",
        value=mission_date("Start Time"),
        layout=widgets.Layout(
            width="auto",
        ),
    )

    stopDate = widgets.DatePicker(
        description="Stop Date:",
        value=mission_date("Stop Time"),
        layout=widgets.Layout(
            width="auto",
        ),
    )

    get_data_button = widgets.Button(
        description="🛰️ Download data 🛰️",
        layout=widgets.Layout(
            width="auto",
        ),
        style=widgets.ButtonStyle(
            button_color=ui_clr["button"]
        ),
    )

    output = widgets.Output()

    # Shared notebook state
    data = {
        "mainStartDate": startDate,
        "mainStopDate": stopDate,
        "missionSelect": mission_select,
        "metakernel": None,
        "missionName": None,
    }

    def on_value_change(change):
        """
        Update date fields when the mission changes.
        """

        startDate.value = mission_date(
            "Start Time"
        )

        stopDate.value = mission_date(
            "Stop Time"
        )

        data["metakernel"] = None
        data["missionName"] = None

    mission_select.observe(
        on_value_change,
        names="value",
    )

    def on_button_clicked(button):
        """
        Download and load the selected mission.
        """

        with output:

            output.clear_output()

            if (
                startDate.value is None
                or stopDate.value is None
            ):
                print(
                    "Please select both dates."
                )
                return

            if startDate.value > stopDate.value:
                print(
                    "Start date must be before "
                    "or equal to stop date."
                )
                return

            mission = missions.iloc[
                mission_select.value
            ]

            mission_name = mission[
                "Mission Name"
            ]

            data_subset = mission[
                "Subset Link"
            ]

            readme_link = mission[
                "Archive Readme"
            ]

            # Invalidate previously loaded selection.
            data["metakernel"] = None
            data["missionName"] = None

            get_data_button.disabled = True

            try:

                metakernel = setup_naif_mission(
                    data_subset=data_subset,
                    start_date=startDate.value,
                    stop_date=stopDate.value,
                    output_dir="/content/NAIF",
                )

                data["metakernel"] = metakernel
                data["missionName"] = mission_name

                display(
                    Markdown(
                        f"#### {mission_name}"
                    )
                )

                display(
                    Markdown(
                        f"Mission information: "
                        f"[NAIF Archive README]"
                        f"({readme_link})"
                    )
                )

                display(
                    Markdown(
                        "---------------------------"
                        "Mission kernels are ready. "
                        "Proceed to target and observer selection."
                    )
                )

            except Exception as error:

                print(
                    f"Download failed: {error}"
                )

                raise

            finally:

                get_data_button.disabled = False

    get_data_button.on_click(
        on_button_clicked
    )

    UI = widgets.GridBox(
        children=[
            mission_select,
            startDate,
            get_data_button,
            stopDate,
        ],
        layout=widgets.Layout(
            width="70%",
            grid_template_columns="300px 300px",
            grid_template_rows="40px 40px",
            grid_gap="10px 20px",
        ),
    )

    display(UI)
    display(output)

    return data

def analyze_data(
    data,
    naif_codes,
    steps=8000,
):
    """
    Create widgets for selecting an observer and up to two
    targets, then calculate their SPICE trajectories.

    The resulting trajectories are combined into one figure,
    but rendering is performed separately in the notebook.
    """

    # ========================================================
    # Identify loaded mission
    # ========================================================

    metakernel = data.get("metakernel")

    if metakernel is None:
        raise RuntimeError(
            "No mission has been loaded. "
            "Please download a mission first."
        )

    mission_dir = Path(metakernel).resolve().parent

    available_ids = get_available_naif_ids(
        mission_dir
    )

    available_objects = (
        naif_codes[
            naif_codes["naif_id"].isin(available_ids)
        ]
        .drop_duplicates(subset="naif_id")
        .sort_values("name")
    )

    object_list = list(
        available_objects[
            ["name", "naif_id"]
        ].itertuples(
            index=False,
            name=None,
        )
    )

    if len(object_list) < 2:
        raise ValueError(
            "At least two available objects are required."
        )

    name_lookup = dict(
        available_objects[
            ["naif_id", "name"]
        ].itertuples(
            index=False,
            name=None,
        )
    )

    # ========================================================
    # Object selection widgets
    # ========================================================

    targetSelect = widgets.Dropdown(
        options=object_list,
        value=object_list[0][1],
        description="Target 1:",
        layout=widgets.Layout(
            width="auto",
        ),
    )

    observerSelect = widgets.Dropdown(
        options=object_list,
        value=object_list[1][1],
        description="Observer:",
        layout=widgets.Layout(
            width="auto",
        ),
    )

    # ========================================================
    # Optional second target
    # ========================================================

    enable_second_target = widgets.Checkbox(
        value=False,
        description="Add second target",
        indent=False,
        disabled=len(object_list) < 3,
    )

    targetSelect2 = widgets.Dropdown(
        options=object_list,
        value=(
            object_list[2][1]
            if len(object_list) >= 3
            else object_list[0][1]
        ),
        description="Target 2:",
        disabled=True,
        layout=widgets.Layout(
            width="auto",
            display="none",
        ),
    )

    def toggle_second_target(change):

        enabled = change["new"]

        targetSelect2.disabled = not enabled

        targetSelect2.layout.display = (
            "" if enabled else "none"
        )

    enable_second_target.observe(
        toggle_second_target,
        names="value",
    )

    # ========================================================
    # Date selection
    # ========================================================

    dataStartDate = widgets.DatePicker(
        description="Start Date:",
        value=data["mainStartDate"].value,
        layout=widgets.Layout(
            width="auto",
        ),
    )

    dataStopDate = widgets.DatePicker(
        description="Stop Date:",
        value=data["mainStopDate"].value,
        layout=widgets.Layout(
            width="auto",
        ),
    )

    # ========================================================
    # Calculate button
    # ========================================================

    calculate_button = widgets.Button(
        description="🚀 Calculate Orbit 🚀",
        layout=widgets.Layout(
            width="auto",
        ),
        style=widgets.ButtonStyle(
            button_color=ui_clr["button"],
        ),
    )

    output = widgets.Output()

    # ========================================================
    # Shared state
    # ========================================================

    data["steps"] = steps

    data["observer"] = ""
    data["observer_id"] = None

    data["target"] = []

    data["plotStartDate"] = dataStartDate
    data["plotStopDate"] = dataStopDate

    data["targetSelect"] = targetSelect
    data["observerSelect"] = observerSelect

    data["targetSelect2"] = targetSelect2
    data["enableSecondTarget"] = enable_second_target

    # ========================================================
    # Calculation callback
    # ========================================================

    def on_button_clicked(button):

        with output:

            output.clear_output(wait=True)

            # ------------------------------------------------
            # Selected objects
            # ------------------------------------------------

            target_id = targetSelect.value
            observer_id = observerSelect.value

            selected_target_ids = [
                target_id
            ]

            if enable_second_target.value:

                selected_target_ids.append(
                    targetSelect2.value
                )

            # ------------------------------------------------
            # Validate object selections
            # ------------------------------------------------

            selected_ids = (
                selected_target_ids + [observer_id]
            )

            if len(set(selected_ids)) != len(selected_ids):

                display(
                    Markdown(
                        "Target(s) and observer must "
                        "all be different objects."
                    )
                )

                return

            # ------------------------------------------------
            # Validate dates
            # ------------------------------------------------

            start_date = dataStartDate.value
            stop_date = dataStopDate.value

            if start_date is None or stop_date is None:

                display(
                    Markdown(
                        "Please select both dates."
                    )
                )

                return

            if start_date >= stop_date:

                display(
                    Markdown(
                        "Start date must be before stop date."
                    )
                )

                return

            download_start = data["mainStartDate"].value
            download_stop = data["mainStopDate"].value

            if (
                start_date < download_start
                or stop_date > download_stop
            ):

                display(
                    Markdown(
                        "Selected dates must be within "
                        "the downloaded mission range."
                    )
                )

                return

            # ------------------------------------------------
            # Prepare target data
            # ------------------------------------------------

            data["target"] = [
                {
                    "id": int(target_id),
                    "name": name_lookup[target_id],
                }
                for target_id in selected_target_ids
            ]

            data["observer"] = name_lookup[observer_id]
            data["observer_id"] = int(observer_id)

            # Clear previous figure
            data.pop("orbit_fig", None)

            # ------------------------------------------------
            # Calculate all trajectories
            # ------------------------------------------------

            try:

                for targetnum in range(
                    len(data["target"])
                ):

                    get_data(
                        data,
                        targetnum=targetnum,
                    )

                # --------------------------------------------
                # Generate combined figure
                # --------------------------------------------

                data["orbit_fig"] = plot_orbit(data)

                # --------------------------------------------
                # Report results
                # --------------------------------------------

                display(
                    Markdown(
                        f"Successfully calculated {len(data['target'])} trajectory(s)."
                    )
                )

                display(
                    Markdown(
                        f"Observer: {data['observer']}"
                    )
                )

                for target in data["target"]:

                    display(
                        Markdown(
                            f"Target: {target['name']}"
                        )
                    )

                display(
                    Markdown(
                        "\nRun the visualization cell to display the combined orbit plot."
                    )
                )

            except Exception as error:

                data.pop("orbit_fig", None)

                display(
                    Markdown(
                        f"Orbit calculation failed: {error}"
                    )
                )

    calculate_button.on_click(
        on_button_clicked
    )

    # ========================================================
    # UI layout
    # ========================================================

    UI = widgets.GridBox(
        children=[
            targetSelect,
            dataStartDate,

            observerSelect,
            dataStopDate,

            enable_second_target,
            targetSelect2,

            calculate_button,
        ],

        layout=widgets.Layout(
            width="70%",

            grid_template_columns="300px 300px",

            grid_template_rows=(
                "40px 40px 40px 40px"
            ),

            grid_gap="10px 20px",
        ),
    )

    display(UI)
    display(output)

    return data