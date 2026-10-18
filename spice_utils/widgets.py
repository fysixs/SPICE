"""
Interactive notebook widgets for SPICE mission selection.
"""

import datetime

import ipywidgets as widgets
from pathlib import Path

from IPython.display import (
    display,
    Markdown,
    HTML
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
                        "Mission kernels are ready. "
                        "Proceed to target and observer "
                        "selection."
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
    Create target/observer selection and orbit plotting widgets.

    Parameters
    ----------
    data : dict
        Shared notebook state from import_data().

    naif_codes : pandas.DataFrame
        NAIF ID/name catalog.

    steps : int
        Number of trajectory samples.
    """

    # --------------------------------------------------------
    # Identify the currently loaded mission
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Object selection widgets
    # --------------------------------------------------------

    targetSelect = widgets.Dropdown(
        options=object_list,
        value=object_list[0][1],
        description="Target:",
        layout=widgets.Layout(
            width="auto",
        ),
    )

    observerSelect = widgets.Dropdown(
        options=[
            item
            for item in object_list
            if item[1] != targetSelect.value
        ],
        description="Observer:",
        layout=widgets.Layout(
            width="auto",
        ),
    )

    # --------------------------------------------------------
    # Keep target and observer mutually exclusive
    # --------------------------------------------------------

    updating = False

    def update_observer_options(change):
        nonlocal updating

        if updating:
            return

        updating = True

        try:
            current_observer = observerSelect.value

            valid_options = [
                item
                for item in object_list
                if item[1] != targetSelect.value
            ]

            observerSelect.options = valid_options

            valid_ids = [
                item[1]
                for item in valid_options
            ]

            if current_observer in valid_ids:
                observerSelect.value = current_observer
            else:
                observerSelect.value = valid_ids[0]

        finally:
            updating = False

    def update_target_options(change):
        nonlocal updating

        if updating:
            return

        updating = True

        try:
            current_target = targetSelect.value

            valid_options = [
                item
                for item in object_list
                if item[1] != observerSelect.value
            ]

            targetSelect.options = valid_options

            valid_ids = [
                item[1]
                for item in valid_options
            ]

            if current_target in valid_ids:
                targetSelect.value = current_target
            else:
                targetSelect.value = valid_ids[0]

        finally:
            updating = False

    targetSelect.observe(
        update_observer_options,
        names="value",
    )

    observerSelect.observe(
        update_target_options,
        names="value",
    )

    # Apply initial filtering in both directions
    update_target_options(None)

    # --------------------------------------------------------
    # Date selection
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Plot button
    # --------------------------------------------------------

    plot_orbit_button = widgets.Button(
        description="🚀 Plot Orbit 🚀",
        layout=widgets.Layout(
            width="auto",
        ),
        style=widgets.ButtonStyle(
            button_color=ui_clr["button"],
        ),
    )

    output = widgets.Output()

    # --------------------------------------------------------
    # Shared state
    # --------------------------------------------------------

    data["steps"] = steps
    data["observer"] = ""
    data["observer_id"] = None
    data["target"] = []

    data["plotStartDate"] = dataStartDate
    data["plotStopDate"] = dataStopDate

    data["targetSelect"] = targetSelect
    data["observerSelect"] = observerSelect

    # --------------------------------------------------------
    # Plot callback
    # --------------------------------------------------------

    def on_button_clicked(button):

        with output:

            output.clear_output(wait=True)

            target_id = targetSelect.value
            observer_id = observerSelect.value

            if target_id == observer_id:
                print(
                    "Target and observer must be different."
                )
                return

            start_date = dataStartDate.value
            stop_date = dataStopDate.value

            if start_date is None or stop_date is None:
                print(
                    "Please select both dates."
                )
                return

            if start_date >= stop_date:
                print(
                    "Start date must be before stop date."
                )
                return

            # Validate against downloaded date range
            download_start = data["mainStartDate"].value
            download_stop = data["mainStopDate"].value

            if (
                start_date < download_start
                or stop_date > download_stop
            ):
                print(
                    "Selected dates must be within "
                    "the downloaded mission range."
                )
                return

            # Resolve display names
            target_name = available_objects.loc[
                available_objects["naif_id"] == target_id,
                "name",
            ].iloc[0]

            observer_name = available_objects.loc[
                available_objects["naif_id"] == observer_id,
                "name",
            ].iloc[0]

            data["target"] = [{
                "id": int(target_id),
                "name": target_name,
            }]

            data["observer"] = observer_name
            data["observer_id"] = int(observer_id)

            try:

                get_data(
                    data,
                    targetnum=0,
                )

                data["orbit_fig"] = plot_orbit(
                    data
                )

                html = data["orbit_fig"].to_html(
                    full_html=True,
                    include_plotlyjs=True
                )

                display(HTML(html))

            except Exception as error:

                print(
                    f"Orbit calculation failed: {error}"
                )

    plot_orbit_button.on_click(
        on_button_clicked
    )

    # --------------------------------------------------------
    # UI layout
    # --------------------------------------------------------

    UI = widgets.GridBox(
        children=[
            targetSelect,
            dataStartDate,
            observerSelect,
            dataStopDate,
            plot_orbit_button,
        ],
        layout=widgets.Layout(
            width="70%",
            grid_template_columns="300px 300px",
            grid_template_rows="40px 40px 40px",
            grid_gap="10px 20px",
        ),
    )

    display(UI)
    display(output)

    return data