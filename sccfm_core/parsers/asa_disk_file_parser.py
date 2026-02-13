from __future__ import annotations

import re

from sccfm_core.models.asa_disk_file import AsaDiskFile, classify_file

# Matches a file line from `dir disk0:` output, e.g.:
#   253      -rwx  21199744     15:30:22 Dec 14 2023  asa917-51-k8.bin
_FILE_LINE_RE = re.compile(
    r"^\s*\d+\s+"  # index number
    r"[-drwx]+\s+"  # permissions
    r"(\d+)\s+"  # file size (capture group 1)
    r"(\d{1,2}:\d{2}:\d{2})\s+"  # time (capture group 2)
    r"(\w{3}\s+\d{1,2}\s+\d{4})\s+"  # date like "Dec 14 2023" (capture group 3)
    r"(\S+)"  # filename (capture group 4)
)


def parse_disk_file_listing(raw_output: str) -> list[AsaDiskFile]:
    """Parse the raw output of an ASA ``dir disk0:`` command.

    Extracts file entries from the listing, skipping header/footer lines
    (e.g. "Directory of disk0:/" and "bytes total" summaries).

    Returns a list of :class:`AsaDiskFile` objects, one per file found.
    """
    files: list[AsaDiskFile] = []
    for line in raw_output.splitlines():
        match = _FILE_LINE_RE.match(line)
        if not match:
            continue
        size_str, time_str, date_str, filename = match.groups()
        files.append(
            AsaDiskFile(
                name=filename,
                size=int(size_str),
                date=f"{date_str} {time_str}",
                file_type=classify_file(filename),
            )
        )
    return files
