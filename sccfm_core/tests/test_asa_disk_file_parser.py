"""Tests for sccfm_core.parsers.asa_disk_file_parser module."""

from __future__ import annotations

from sccfm_core.models.asa_disk_file import AsaDiskFile, AsaDiskFileType
from sccfm_core.parsers.asa_disk_file_parser import parse_disk_file_listing

SAMPLE_DIR_OUTPUT = """\
Directory of disk0:/

253      -rwx  21199744     15:30:22 Dec 14 2023  asa917-51-k8.bin
254      -rwx  12345678     10:20:30 Jan 05 2024  anyconnect-win-4.10.06079-webdeploy-k9.pkg
255      -rwx  9876543      10:20:30 Jan 05 2024  anyconnect-macos-4.10.06079-webdeploy-k9.pkg
256      -rwx  56789012     11:15:00 Feb 10 2024  asdm-7181.bin
257      -rwx  1024         09:00:00 Mar 01 2024  sdesktop_log.txt

255426560 bytes total (120512512 bytes free)
"""


class TestParseDiskFileListing:
    """Tests for parse_disk_file_listing()."""

    def test_should_parse_all_files_from_valid_output(self) -> None:
        """Parser should extract every file entry from a dir listing."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        assert len(files) == 5

    def test_should_extract_filenames(self) -> None:
        """Parser should extract correct filenames."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        names = [f.name for f in files]
        assert names == [
            "asa917-51-k8.bin",
            "anyconnect-win-4.10.06079-webdeploy-k9.pkg",
            "anyconnect-macos-4.10.06079-webdeploy-k9.pkg",
            "asdm-7181.bin",
            "sdesktop_log.txt",
        ]

    def test_should_extract_sizes(self) -> None:
        """Parser should extract correct file sizes as integers."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        sizes = [f.size for f in files]
        assert sizes == [21199744, 12345678, 9876543, 56789012, 1024]

    def test_should_extract_dates(self) -> None:
        """Parser should combine date and time into a single string."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        assert files[0].date == "Dec 14 2023 15:30:22"
        assert files[3].date == "Feb 10 2024 11:15:00"

    def test_should_classify_os_image(self) -> None:
        """Parser should classify asa*.bin as OS_IMAGE."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        assert files[0].file_type == AsaDiskFileType.OS_IMAGE

    def test_should_classify_anyconnect_packages(self) -> None:
        """Parser should classify anyconnect*.pkg as ANYCONNECT_PACKAGE."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        assert files[1].file_type == AsaDiskFileType.ANYCONNECT_PACKAGE
        assert files[2].file_type == AsaDiskFileType.ANYCONNECT_PACKAGE

    def test_should_classify_asdm_image(self) -> None:
        """Parser should classify asdm*.bin as ASDM_IMAGE."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        assert files[3].file_type == AsaDiskFileType.ASDM_IMAGE

    def test_should_classify_other_files(self) -> None:
        """Parser should classify unrecognised files as OTHER."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        assert files[4].file_type == AsaDiskFileType.OTHER

    def test_should_return_empty_list_for_empty_disk(self) -> None:
        """Parser should return an empty list when no files are present."""
        output = """\
Directory of disk0:/

0 bytes total (0 bytes free)
"""
        files = parse_disk_file_listing(output)
        assert files == []

    def test_should_return_empty_list_for_empty_string(self) -> None:
        """Parser should return an empty list for empty input."""
        assert parse_disk_file_listing("") == []

    def test_should_skip_malformed_lines(self) -> None:
        """Parser should silently skip lines that do not match the expected format."""
        output = """\
Directory of disk0:/
this is a malformed line
another bad line 12345
253      -rwx  21199744     15:30:22 Dec 14 2023  asa917-51-k8.bin
random garbage
"""
        files = parse_disk_file_listing(output)
        assert len(files) == 1
        assert files[0].name == "asa917-51-k8.bin"

    def test_should_return_frozen_dataclass_instances(self) -> None:
        """Parsed files should be immutable frozen dataclass instances."""
        files = parse_disk_file_listing(SAMPLE_DIR_OUTPUT)
        file_entry = files[0]
        assert isinstance(file_entry, AsaDiskFile)
        # Verify frozen
        try:
            file_entry.name = "changed"
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass
