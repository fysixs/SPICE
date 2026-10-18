"""
SPICE geometry and trajectory calculations.
"""

import datetime

import numpy as np
import spiceypy as spice


def et2datetime(time_et):
    """
    Convert SPICE ephemeris time to a Python UTC datetime.
    """

    utc = spice.et2utc(
        float(time_et),
        "ISOC",
        6
    )

    return datetime.datetime.fromisoformat(utc)


def calculate_trajectory(
    target_id,
    observer_id,
    start_date,
    stop_date,
    steps=8000,
    reference_frame="J2000",
    aberration="NONE",
):
    """
    Calculate the position and velocity of a target
    relative to an observer.

    Parameters
    ----------
    target_id : int
        NAIF ID of the target.

    observer_id : int
        NAIF ID of the observer.

    start_date, stop_date : datetime.date
        Requested time range.

    steps : int
        Number of time samples.

    reference_frame : str
        SPICE reference frame.

    aberration : str
        Aberration correction.

    Returns
    -------
    dict
        Time, position, velocity, and light-time arrays.
    """

    if target_id == observer_id:
        raise ValueError(
            "Target and observer must be different objects."
        )

    if start_date is None or stop_date is None:
        raise ValueError(
            "Both start and stop dates are required."
        )

    if start_date >= stop_date:
        raise ValueError(
            "Start date must be before stop date."
        )

    if steps < 2:
        raise ValueError(
            "At least two time samples are required."
        )

    et_start = spice.str2et(
        start_date.isoformat()
    )

    et_stop = spice.str2et(
        stop_date.isoformat()
    )

    times = np.linspace(
        et_start,
        et_stop,
        steps
    )

    states, light_times = spice.spkezr(
        str(target_id),
        times,
        reference_frame,
        aberration,
        str(observer_id),
    )

    states = np.asarray(states)

    return {
        "ET": times,
        "UTC": [
            et2datetime(t)
            for t in times
        ],
        "lt": np.asarray(light_times),
        "rx": states[:, 0],
        "ry": states[:, 1],
        "rz": states[:, 2],
        "vx": states[:, 3],
        "vy": states[:, 4],
        "vz": states[:, 5],
    }


def get_data(data, targetnum=0):
    """
    Compatibility wrapper for the notebook's data dictionary.

    Updates the selected target with calculated trajectory data.
    """

    target = data["target"][targetnum]

    result = calculate_trajectory(
        target_id=target["id"],
        observer_id=data["observer_id"],
        start_date=data["plotStartDate"].value,
        stop_date=data["plotStopDate"].value,
        steps=data["steps"],
    )

    data["t"] = {
        "ET": result["ET"],
        "UTC": result["UTC"],
    }

    for key in (
        "lt",
        "rx",
        "ry",
        "rz",
        "vx",
        "vy",
        "vz",
    ):
        target[key] = result[key]

    return data