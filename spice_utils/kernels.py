"""
SPICE kernel download, configuration, and loading utilities.
"""

import hashlib
import json
import re
import shutil
import zipfile

from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
import spiceypy as spice

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm.auto import tqdm


DEFAULT_DATA_DIR = Path("/content/NAIF")


def _create_session():
    """Create a requests session with retry support."""

    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )

    adapter = HTTPAdapter(max_retries=retries)

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def _dataset_identifier(data_subset, start_date, stop_date):
    """
    Generate a unique identifier for a mission/date selection.
    """

    key = (
        f"{data_subset}|"
        f"{start_date.isoformat()}|"
        f"{stop_date.isoformat()}"
    )

    return hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()[:12]


def download_spice_kernels(
    manifest_path,
    output_dir=None,
    cut_dirs=5,
    overwrite=False,
):
    """
    Download SPICE kernels listed in a NAIF URL manifest.

    Parameters
    ----------
    manifest_path : str or Path
        NAIF-generated urls_*.txt manifest.

    output_dir : str or Path, optional
        Destination directory.

    cut_dirs : int
        Number of leading URL path components to remove.

    overwrite : bool
        Replace existing kernel files.

    Returns
    -------
    list[Path]
        Paths to downloaded kernel files.
    """

    manifest_path = Path(manifest_path).resolve()

    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    if output_dir is None:
        output_dir = manifest_path.parent

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    urls = [
        line.strip()
        for line in manifest_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    downloaded_files = []

    print(f"Found {len(urls)} kernel URLs")

    with _create_session() as session:

        for url in tqdm(
            urls,
            desc="Downloading SPICE kernels",
        ):

            parsed = urlparse(url)

            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"Unsupported kernel URL: {url}"
                )

            components = [
                component
                for component in parsed.path.split("/")
                if component
            ]

            remaining = components[cut_dirs:]

            if not remaining:
                raise ValueError(
                    f"Invalid kernel URL path: {url}"
                )

            relative_path = Path(*remaining)

            # Prevent unsafe paths in manifests.
            if any(
                part in (".", "..")
                for part in relative_path.parts
            ):
                raise ValueError(
                    f"Unsafe kernel path: {url}"
                )

            destination = output_dir / relative_path

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if destination.is_file() and not overwrite:
                downloaded_files.append(destination)
                continue

            temp_path = destination.with_name(
                destination.name + ".part"
            )

            try:
                with session.get(
                    url,
                    stream=True,
                    timeout=(30, 300),
                ) as response:

                    response.raise_for_status()

                    with temp_path.open("wb") as file:
                        for chunk in response.iter_content(
                            chunk_size=1024 * 1024
                        ):
                            if chunk:
                                file.write(chunk)

                temp_path.replace(destination)

            finally:
                if temp_path.exists():
                    temp_path.unlink()

            downloaded_files.append(destination)

    print(
        f"Completed: {len(downloaded_files)} files"
    )

    return downloaded_files


def _safe_extract_zip(archive_path, output_dir):
    """
    Extract a ZIP archive while preventing path traversal.
    """

    output_dir = Path(output_dir).resolve()

    with zipfile.ZipFile(archive_path) as archive:

        for member in archive.infolist():

            destination = (
                output_dir / member.filename
            ).resolve()

            if not destination.is_relative_to(output_dir):
                raise ValueError(
                    f"Unsafe archive member: {member.filename}"
                )

        archive.extractall(output_dir)


def download_naif_data(
    data_subset,
    start_date,
    stop_date,
    output_dir=DEFAULT_DATA_DIR,
    overwrite=False,
):
    """
    Download a NAIF mission subset and its SPICE kernels.

    Each mission/date-range combination is stored separately.

    Returns
    -------
    Path
        Directory containing the selected dataset.
    """

    if not isinstance(start_date, date):
        raise TypeError("start_date must be a date")

    if not isinstance(stop_date, date):
        raise TypeError("stop_date must be a date")

    if start_date > stop_date:
        raise ValueError(
            "Start date must not exceed stop date."
        )

    output_dir = Path(output_dir).resolve()

    dataset_id = _dataset_identifier(
        data_subset,
        start_date,
        stop_date,
    )

    mission_dir = output_dir / dataset_id

    archive_path = mission_dir / "data.zip"
    completion_marker = (
        mission_dir / ".download_complete"
    )

    if mission_dir.exists():

        if overwrite:
            shutil.rmtree(mission_dir)

        elif completion_marker.exists():
            print(
                f"Using cached dataset: {mission_dir}"
            )
            return mission_dir

    mission_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    params = {
        "start": start_date.isoformat(),
        "stop": stop_date.isoformat(),
        "action": "Subset",
    }

    separator = (
        "&" if "?" in data_subset else "?"
    )

    url = (
        f"{data_subset}"
        f"{separator}"
        f"{urlencode(params)}"
    )

    if not archive_path.exists():

        print("Downloading NAIF archive...")

        temp_archive = archive_path.with_name(
            "data.zip.part"
        )

        try:
            with requests.get(
                url,
                stream=True,
                timeout=(30, 300),
            ) as response:

                response.raise_for_status()

                with temp_archive.open("wb") as file:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            file.write(chunk)

            temp_archive.replace(archive_path)

        finally:
            if temp_archive.exists():
                temp_archive.unlink()

    manifests = list(
        mission_dir.glob("urls_*.txt")
    )

    if not manifests:

        print("Extracting NAIF archive...")

        _safe_extract_zip(
            archive_path,
            mission_dir,
        )

        manifests = list(
            mission_dir.glob("urls_*.txt")
        )

    if len(manifests) != 1:
        raise RuntimeError(
            "Expected exactly one URL manifest; "
            f"found {len(manifests)}"
        )

    print("Downloading SPICE kernels...")

    download_spice_kernels(
        manifest_path=manifests[0],
        output_dir=mission_dir,
        overwrite=overwrite,
    )

    completion_marker.touch()

    print(
        f"NAIF dataset ready: {mission_dir}"
    )

    return mission_dir


def configure_metakernel(
    metakernel_path,
    kernels_dir,
    output_path=None,
    validate=True,
):
    """
    Configure a SPICE meta-kernel for local kernel paths.
    """

    metakernel_path = Path(
        metakernel_path
    ).resolve()

    kernels_dir = Path(
        kernels_dir
    ).resolve()

    if not metakernel_path.is_file():
        raise FileNotFoundError(
            metakernel_path
        )

    if not kernels_dir.is_dir():
        raise NotADirectoryError(
            kernels_dir
        )

    if output_path is None:
        output_path = metakernel_path.with_name(
            f"{metakernel_path.stem}_local.tm"
        )
    else:
        output_path = Path(
            output_path
        ).resolve()

    text = metakernel_path.read_text(
        encoding="utf-8"
    )

    pattern = re.compile(
        r"(PATH_VALUES\s*=\s*\()"
        r"(.*?)"
        r"(\))",
        re.DOTALL,
    )

    match = pattern.search(text)

    if not match:
        raise ValueError(
            "PATH_VALUES not found in meta-kernel."
        )

    kernel_path = kernels_dir.as_posix()

    replacement = (
        match.group(1)
        + f"\n    '{kernel_path}'\n"
        + match.group(3)
    )

    modified_text = (
        text[:match.start()]
        + replacement
        + text[match.end():]
    )

    if validate:

        kernel_pattern = re.compile(
            r"'\$KERNELS/([^']+)'"
        )

        kernel_files = kernel_pattern.findall(
            modified_text
        )

        missing = [
            kernel
            for kernel in kernel_files
            if not (
                kernels_dir / kernel
            ).is_file()
        ]

        if missing:
            raise FileNotFoundError(
                "Missing kernel files:\n"
                + "\n".join(missing)
            )

        print(
            f"Validated {len(kernel_files)} "
            "kernel references."
        )

    output_path.write_text(
        modified_text,
        encoding="utf-8",
    )

    print(
        f"Meta-kernel saved: {output_path}"
    )

    return output_path


def prepare_metakernel(mission_dir):
    """
    Generate a local SPICE meta-kernel from downloaded NAIF kernels.

    Recursively discovers kernel files without assuming a
    specific archive directory structure.

    Parameters
    ----------
    mission_dir : str or Path
        Directory containing the downloaded mission data.

    Returns
    -------
    Path
        Path to the generated meta-kernel.
    """

    from pathlib import Path

    mission_dir = Path(mission_dir).resolve()

    # --------------------------------------------------------
    # Discover SPICE kernel files
    # --------------------------------------------------------

    kernel_extensions = {
        ".bsp",   # SPK
        ".bc",    # CK
        ".bpc",   # Binary PCK
        ".tls",   # Leap seconds
        ".tpc",   # Text PCK
        ".tf",    # Frame kernels
        ".ti",    # Instrument kernels
        ".tsc",   # Spacecraft clock
        ".bds",   # Digital shape kernels
    }

    kernel_files = sorted(
        path
        for path in mission_dir.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower() in kernel_extensions
        )
    )

    if not kernel_files:
        raise RuntimeError(
            f"No SPICE kernels found in {mission_dir}"
        )

    print(
        f"Found {len(kernel_files)} SPICE kernels."
    )

    # --------------------------------------------------------
    # Construct meta-kernel
    # --------------------------------------------------------

    metakernel_path = mission_dir / "local_meta.tm"

    kernel_entries = []

    for kernel in kernel_files:

        # Absolute paths avoid working-directory issues
        kernel_path = kernel.resolve().as_posix()

        # Escape single quotes for SPICE text syntax
        kernel_path = kernel_path.replace(
            "'",
            "''",
        )

        kernel_entries.append(
            f"    '{kernel_path}'"
        )

    kernel_list = ",\n".join(
        kernel_entries
    )

    metakernel_content = (
        "KPL/MK\n\n"
        "\\begindata\n\n"
        "KERNELS_TO_LOAD = (\n"
        f"{kernel_list}\n"
        ")\n\n"
        "\\begintext\n"
    )

    metakernel_path.write_text(
        metakernel_content,
        encoding="utf-8",
    )

    print(
        f"Meta-kernel created: {metakernel_path}"
    )

    return metakernel_path


def load_naif_kernels(
    metakernel,
    clear_existing=True,
):
    """
    Load a configured NAIF meta-kernel into SPICE.
    """

    metakernel = Path(
        metakernel
    ).resolve()

    if not metakernel.is_file():
        raise FileNotFoundError(
            metakernel
        )

    if clear_existing:
        spice.kclear()

    spice.furnsh(
        str(metakernel)
    )

    print(
        f"Loaded meta-kernel: {metakernel}"
    )

    print(
        "Total loaded kernels: "
        f"{spice.ktotal('ALL')}"
    )


def setup_naif_mission(
    data_subset,
    start_date,
    stop_date,
    output_dir=DEFAULT_DATA_DIR,
    overwrite=False,
):
    """
    Download, configure, and load a NAIF mission.
    """

    print("#### GETTING DATA FROM NAIF ####")

    mission_dir = download_naif_data(
        data_subset=data_subset,
        start_date=start_date,
        stop_date=stop_date,
        output_dir=output_dir,
        overwrite=overwrite,
    )

    print("#### CONFIGURING META-KERNEL ####")

    metakernel = prepare_metakernel(
        mission_dir
    )

    print("#### CONNECTING KERNELS ####")

    load_naif_kernels(
        metakernel
    )

    return metakernel


def get_available_naif_ids(mission_dir):
    """
    Extract unique NAIF object IDs from mission SPK files.

    Returns
    -------
    list[int]
        Sorted NAIF IDs.
    """

    mission_dir = Path(
        mission_dir
    ).resolve()

    spk_files = list(
        mission_dir.rglob("*.bsp")
    )

    if not spk_files:
        raise FileNotFoundError(
            "No SPK files found."
        )

    naif_ids = set()

    for spk_file in spk_files:

        ids = spice.spkobj(
            str(spk_file)
        )

        naif_ids.update(ids)

    return sorted(naif_ids)