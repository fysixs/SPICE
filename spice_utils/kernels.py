"""
SPICE kernel download, configuration, and loading utilities.
"""

import hashlib
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


# ============================================================
# Meta-kernel helpers
# ============================================================

def _parse_metakernel_entries(metakernel_path):
    """
    Extract PATH_VALUES, PATH_SYMBOLS, and KERNELS_TO_LOAD
    from a NAIF meta-kernel.

    Returns
    -------
    list[Path]
        Absolute paths to referenced kernel files.
    """

    metakernel_path = Path(metakernel_path).resolve()

    content = metakernel_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    # Only parse data sections, not explanatory comments.
    data_sections = re.findall(
        r"\\begindata(.*?)(?=\\begintext|\\begindata|\Z)",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    data_content = "\n".join(data_sections)

    def get_values(variable):
        """
        Extract quoted string values from a meta-kernel
        variable assignment.
        """

        pattern = (
            rf"\b{re.escape(variable)}\s*"
            rf"(?:=|\+=)\s*\((.*?)\)"
        )

        matches = re.findall(
            pattern,
            data_content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        values = []

        for match in matches:
            values.extend(
                re.findall(
                    r"'((?:[^']|'')*)'",
                    match,
                )
            )

        return [
            value.replace("''", "'")
            for value in values
        ]

    path_symbols = get_values("PATH_SYMBOLS")
    path_values = get_values("PATH_VALUES")
    kernel_entries = get_values("KERNELS_TO_LOAD")

    if len(path_symbols) != len(path_values):
        raise ValueError(
            f"PATH_SYMBOLS and PATH_VALUES mismatch "
            f"in {metakernel_path.name}"
        )

    # Resolve NAIF path symbols.
    symbol_map = dict(
        zip(path_symbols, path_values)
    )

    resolved_kernels = []

    for entry in kernel_entries:

        resolved = entry

        for symbol, value in symbol_map.items():
            resolved = resolved.replace(
                f"${symbol}",
                value,
            )

        kernel_path = Path(resolved)

        if not kernel_path.is_absolute():

            candidate = (
                metakernel_path.parent / kernel_path
            ).resolve()

            if candidate.is_file():

                kernel_path = candidate

            else:

                # NAIF subset archives sometimes place the
                # actual data directory inside a named folder
                # such as cosp_1000/data/.

                matching_files = list(
                    metakernel_path.parent.rglob(
                        kernel_path.name
                    )
                )

                # Match the complete trailing path, not
                # just the filename.
                matching_files = [
                    path
                    for path in matching_files
                    if path.as_posix().endswith(
                        kernel_path.as_posix().lstrip("./")
                    )
                ]

                if len(matching_files) == 1:

                    kernel_path = matching_files[0]

                elif len(matching_files) == 0:

                    raise FileNotFoundError(
                        f"Kernel referenced by "
                        f"{metakernel_path.name} "
                        f"was not found: {resolved}"
                    )

                else:

                    raise RuntimeError(
                        f"Ambiguous kernel reference "
                        f"in {metakernel_path.name}: "
                        f"{resolved}"
                    )

        resolved_kernels.append(
            kernel_path.resolve()
        )

    return resolved_kernels


def _deduplicate_kernels(kernel_paths):
    """
    Remove duplicate kernel references while preserving
    their final occurrence and loading order.
    """

    seen = set()
    result = []

    for path in reversed(kernel_paths):

        normalized = str(Path(path).resolve())

        if normalized not in seen:
            seen.add(normalized)
            result.append(Path(normalized))

    return list(reversed(result))


# ============================================================
# Prepare local meta-kernel
# ============================================================

def prepare_metakernel(mission_dir):
    """
    Generate a local meta-kernel by combining the original
    NAIF meta-kernels.

    Preserves kernel loading order and uses SPICE path
    symbols to avoid long absolute kernel filenames.

    Parameters
    ----------
    mission_dir : str or Path
        Directory containing extracted NAIF mission data.

    Returns
    -------
    Path
        Path to the generated local meta-kernel.
    """

    mission_dir = Path(mission_dir).resolve()

    print("Searching for original NAIF meta-kernels...")

    # --------------------------------------------------------
    # Discover original meta-kernels
    # --------------------------------------------------------

    metakernels = sorted(
        path
        for path in mission_dir.rglob("*.tm")
        if path.name != "local_meta.tm"
    )

    if not metakernels:
        raise RuntimeError(
            "No original NAIF meta-kernels found in "
            f"{mission_dir}"
        )

    print(
        f"Found {len(metakernels)} original meta-kernel(s)."
    )

    for metakernel in metakernels:
        print(f"  - {metakernel.name}")

    # --------------------------------------------------------
    # Parse original kernel references
    # --------------------------------------------------------

    all_kernels = []

    for metakernel in metakernels:

        kernel_paths = _parse_metakernel_entries(
            metakernel
        )

        print(
            f"{metakernel.name}: "
            f"{len(kernel_paths)} kernel references"
        )

        all_kernels.extend(kernel_paths)

    # --------------------------------------------------------
    # Remove duplicate references
    # --------------------------------------------------------

    kernel_files = _deduplicate_kernels(
        all_kernels
    )

    print(
        f"Found {len(kernel_files)} unique kernel references."
    )

    # --------------------------------------------------------
    # Validate referenced files
    # --------------------------------------------------------

    missing = [
        path
        for path in kernel_files
        if not path.is_file()
    ]

    if missing:

        print("\nMissing kernel files:")

        for path in missing[:20]:
            print(f"  - {path}")

        raise FileNotFoundError(
            f"{len(missing)} referenced kernels "
            "could not be found."
        )

    # --------------------------------------------------------
    # Build path-symbol mapping
    # --------------------------------------------------------

    # Use the mission directory as the common root.
    #
    # Individual references are converted into paths
    # relative to this directory.

    root_path = mission_dir.as_posix()

    kernel_entries = []

    for kernel in kernel_files:

        relative_path = kernel.relative_to(
            mission_dir
        ).as_posix()

        kernel_entries.append(
            f"$KERNELS/{relative_path}"
        )

    # --------------------------------------------------------
    # Validate SPICE string lengths
    # --------------------------------------------------------

    # SPICE text kernels impose a limit on individual
    # string values. Keep each generated path within
    # the supported length.

    for entry in kernel_entries:

        if len(entry) > 80:
            raise ValueError(
                "Kernel reference exceeds 80 characters: "
                f"{entry}"
            )

    if len(root_path) > 80:
        raise ValueError(
            "Mission directory path exceeds "
            "the SPICE string length limit."
        )

    # --------------------------------------------------------
    # Generate local meta-kernel
    # --------------------------------------------------------

    metakernel_path = (
        mission_dir / "local_meta.tm"
    )

    def quote_spice(value):
        return "'" + value.replace("'", "''") + "'"

    kernel_lines = "\n".join(
        f"    {quote_spice(entry)}"
        for entry in kernel_entries
    )

    metakernel_content = (
        "KPL/MK\n\n"
        "\\begindata\n\n"
        "PATH_VALUES = (\n"
        f"    {quote_spice(root_path)}\n"
        ")\n\n"
        "PATH_SYMBOLS = (\n"
        "    'KERNELS'\n"
        ")\n\n"
        "KERNELS_TO_LOAD = (\n"
        f"{kernel_lines}\n"
        ")\n\n"
        "\\begintext\n"
    )

    metakernel_path.write_text(
        metakernel_content,
        encoding="utf-8",
    )

    print(
        f"Local meta-kernel created: {metakernel_path}"
    )

    print(
        f"Total kernels configured: {len(kernel_files)}"
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