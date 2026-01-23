"""
Integration tests for CLI mode argument parsing.

Tests that the argparse configuration correctly handles mode flags
and sets the mode value appropriately.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
script_dir = Path(__file__).resolve().parent
tests_dir = script_dir.parent
project_root = tests_dir.parent
src_dir = project_root / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def create_test_parser():
    """
    Create a minimal parser with the same mode flag structure as main.py.

    This is a test double of the actual CLI parser to avoid importing
    the full main.py module with all its side effects.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("newspaper", nargs="?")

    # New mode flags
    parser.add_argument(
        "--update",
        action="store_const",
        const="update",
        dest="mode",
    )
    parser.add_argument(
        "--resume",
        action="store_const",
        const="resume",
        dest="mode",
    )
    parser.add_argument(
        "--full-discovery",
        action="store_const",
        const="full_discovery",
        dest="mode",
    )
    parser.add_argument(
        "--full-from-scratch",
        action="store_const",
        const="full_from_scratch",
        dest="mode",
    )

    # Deprecated flags (backwards compatibility)
    parser.add_argument(
        "--discover",
        action="store_const",
        const="update",
        dest="mode",
    )
    parser.add_argument(
        "--discover-full",
        action="store_const",
        const="full_discovery",
        dest="mode",
    )

    # Set default
    parser.set_defaults(mode="update")

    return parser


class TestCliModeArguments:
    """Tests for CLI mode argument parsing."""

    def test_default_mode_is_update(self):
        """Test that default mode is 'update' when no flag specified."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc"])
        assert args.mode == "update"

    def test_update_flag_sets_mode(self):
        """Test --update flag sets mode to 'update'."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--update"])
        assert args.mode == "update"

    def test_resume_flag_sets_mode(self):
        """Test --resume flag sets mode to 'resume'."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--resume"])
        assert args.mode == "resume"

    def test_full_discovery_flag_sets_mode(self):
        """Test --full-discovery flag sets mode to 'full_discovery'."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--full-discovery"])
        assert args.mode == "full_discovery"

    def test_full_from_scratch_flag_sets_mode(self):
        """Test --full-from-scratch flag sets mode to 'full_from_scratch'."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--full-from-scratch"])
        assert args.mode == "full_from_scratch"

    def test_deprecated_discover_flag_maps_to_update(self):
        """Test deprecated --discover flag maps to 'update' mode."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--discover"])
        assert args.mode == "update"

    def test_deprecated_discover_full_flag_maps_to_full_discovery(self):
        """Test deprecated --discover-full flag maps to 'full_discovery' mode."""
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--discover-full"])
        assert args.mode == "full_discovery"

    def test_last_flag_wins_when_multiple_specified(self):
        """
        Test that when multiple mode flags are specified, the last one wins.

        This is the default argparse behavior when using store_const with dest.
        """
        parser = create_test_parser()
        args = parser.parse_args(["sibc", "--update", "--resume"])
        assert args.mode == "resume"

        args = parser.parse_args(["sibc", "--resume", "--full-discovery"])
        assert args.mode == "full_discovery"

    def test_mode_with_no_newspaper_arg(self):
        """Test mode is still set correctly when newspaper arg is omitted."""
        parser = create_test_parser()
        args = parser.parse_args(["--resume"])
        assert args.mode == "resume"

    def test_all_mode_flags_exist(self):
        """Test that all 4 primary mode flags are recognized by parser."""
        parser = create_test_parser()

        # Should not raise an error
        parser.parse_args(["sibc", "--update"])
        parser.parse_args(["sibc", "--resume"])
        parser.parse_args(["sibc", "--full-discovery"])
        parser.parse_args(["sibc", "--full-from-scratch"])

    def test_backwards_compat_flags_still_work(self):
        """Test that deprecated flags still work for backwards compatibility."""
        parser = create_test_parser()

        # Should not raise an error
        parser.parse_args(["sibc", "--discover"])
        parser.parse_args(["sibc", "--discover-full"])
