"""
NAIF catalog retrieval and parsing utilities.
"""

import re
from urllib.parse import urljoin

import pandas as pd
import requests

from bs4 import BeautifulSoup, Comment

from .config import (
    NAIF_ARCHIVE_URL,
    NAIF_IDS_URL,
)


def get_archived_missions():
    """
    Retrieve the archived mission catalog from NAIF.

    Returns
    -------
    pd.DataFrame
        Archived mission information.

    Raises
    ------
    requests.RequestException
        If the request fails.

    ValueError
        If the expected mission table cannot be parsed.
    """

    response = requests.get(
        NAIF_ARCHIVE_URL,
        timeout=30,
    )

    response.raise_for_status()

    # Preserve the original extraction boundary:
    # <!--start data--> ... <!--end data-->
    html = response.text

    start_match = re.search(
        r"<!--\s*start data\s*-->",
        html,
        flags=re.IGNORECASE,
    )

    end_match = re.search(
        r"<!--\s*end data\s*-->",
        html,
        flags=re.IGNORECASE,
    )

    if (
        start_match is None
        or end_match is None
        or end_match.start() <= start_match.end()
    ):
        raise ValueError(
            "Could not locate NAIF archived data section."
        )

    table_html = html[
        start_match.end():end_match.start()
    ]

    soup = BeautifulSoup(
        table_html,
        "html.parser",
    )

    table = soup.find("table")

    if table is None:
        raise ValueError(
            "Could not locate archived mission table."
        )

    rows = table.find_all("tr")

    if not rows:
        raise ValueError(
            "Archived mission table is empty."
        )

    # Extract column headers
    headers = [
        cell.get_text(strip=True)
        for cell in rows[0].find_all(
            ["th", "td"],
            recursive=False,
        )
    ]

    records = []

    # Extract mission records
    for row in rows[1:]:

        cells = row.find_all(
            ["td", "th"],
            recursive=False,
        )

        record = []

        for cell in cells:

            link = cell.find("a", href=True)

            if link:
                value = urljoin(
                    NAIF_ARCHIVE_URL,
                    link["href"],
                )
            else:
                value = cell.get_text(
                    strip=True
                )

            record.append(value)

        if len(record) == len(headers):
            records.append(record)

    if not records:
        raise ValueError(
            "No archived mission records were found."
        )

    return pd.DataFrame(
        records,
        columns=headers,
    )


def get_naif_ids():
    """
    Retrieve NAIF object identifiers and names.

    Preserves aliases while removing duplicate
    (naif_id, name) combinations.

    Returns
    -------
    pd.DataFrame
        Columns:
        - naif_id
        - name
    """

    response = requests.get(
        NAIF_IDS_URL,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    pattern = re.compile(
        r"^\s*(-?\d+)\s+'([^']+)'"
    )

    records = []

    for pre in soup.find_all("pre"):

        text = pre.get_text()

        if "NAIF ID" not in text:
            continue

        for line in text.splitlines():

            match = pattern.match(line)

            if match:

                records.append({
                    "naif_id": int(match.group(1)),
                    "name": match.group(2).strip(),
                })

    if not records:
        raise ValueError(
            "No NAIF identifiers were found. "
            "The source format may have changed."
        )

    df = pd.DataFrame(
        records,
        columns=["naif_id", "name"],
    )

    df = (
        df.drop_duplicates(
            subset=["naif_id", "name"]
        )
        .sort_values(
            by=["naif_id", "name"]
        )
        .reset_index(drop=True)
    )

    return df