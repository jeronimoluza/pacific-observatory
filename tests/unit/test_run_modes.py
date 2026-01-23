"""
Unit tests for run mode functionality.

Tests the ScrapeMode enum and mode_from_string() mapping function
to ensure CLI mode arguments correctly map to internal mode values.
"""

import pytest
from text.scrapers.modes import ScrapeMode, mode_from_string


class TestScrapeModeEnum:
    """Tests for the ScrapeMode enum."""

    def test_mode_enum_has_all_modes(self):
        """Verify all 4 modes exist in ScrapeMode enum."""
        assert hasattr(ScrapeMode, "UPDATE")
        assert hasattr(ScrapeMode, "RESUME")
        assert hasattr(ScrapeMode, "FULL_DISCOVERY")
        assert hasattr(ScrapeMode, "FULL_FROM_SCRATCH")

    def test_mode_enum_values(self):
        """Verify enum values are correct strings."""
        assert ScrapeMode.UPDATE.value == "update"
        assert ScrapeMode.RESUME.value == "resume"
        assert ScrapeMode.FULL_DISCOVERY.value == "full_discovery"
        assert ScrapeMode.FULL_FROM_SCRATCH.value == "full_from_scratch"

    def test_mode_enum_count(self):
        """Verify exactly 4 modes exist (no extras)."""
        assert len(ScrapeMode) == 4


class TestModeFromString:
    """Tests for the mode_from_string() function."""

    def test_mode_from_string_update(self):
        """Test 'update' maps to UPDATE mode."""
        assert mode_from_string("update") == ScrapeMode.UPDATE

    def test_mode_from_string_resume(self):
        """Test 'resume' maps to RESUME mode."""
        assert mode_from_string("resume") == ScrapeMode.RESUME

    def test_mode_from_string_full_discovery(self):
        """Test 'full_discovery' maps to FULL_DISCOVERY mode."""
        assert mode_from_string("full_discovery") == ScrapeMode.FULL_DISCOVERY

    def test_mode_from_string_full_from_scratch(self):
        """Test 'full_from_scratch' maps to FULL_FROM_SCRATCH mode."""
        assert mode_from_string("full_from_scratch") == ScrapeMode.FULL_FROM_SCRATCH

    def test_mode_from_string_with_hyphens(self):
        """Test hyphenated CLI strings map correctly."""
        assert mode_from_string("full-discovery") == ScrapeMode.FULL_DISCOVERY

    def test_mode_from_string_case_insensitive(self):
        """Test mode_from_string is case insensitive."""
        assert mode_from_string("UPDATE") == ScrapeMode.UPDATE
        assert mode_from_string("Resume") == ScrapeMode.RESUME
        assert mode_from_string("FULL-DISCOVERY") == ScrapeMode.FULL_DISCOVERY

    def test_mode_from_string_with_whitespace(self):
        """Test mode_from_string handles leading/trailing whitespace."""
        assert mode_from_string("  update  ") == ScrapeMode.UPDATE
        assert mode_from_string("\tresume\n") == ScrapeMode.RESUME

    def test_mode_from_string_default_alias(self):
        """Test 'default' maps to UPDATE mode."""
        assert mode_from_string("default") == ScrapeMode.UPDATE

    def test_mode_from_string_legacy_discover_alias(self):
        """Test 'discover' maps to UPDATE mode (backwards compat)."""
        assert mode_from_string("discover") == ScrapeMode.UPDATE

    def test_mode_from_string_legacy_discover_full_alias(self):
        """Test 'discover-full' maps to FULL_DISCOVERY mode (backwards compat)."""
        assert mode_from_string("discover-full") == ScrapeMode.FULL_DISCOVERY

    def test_mode_from_string_legacy_full_alias(self):
        """Test 'full' maps to FULL_FROM_SCRATCH mode (backwards compat)."""
        assert mode_from_string("full") == ScrapeMode.FULL_FROM_SCRATCH

    def test_mode_from_string_legacy_full_scrape_alias(self):
        """Test 'full-scrape' maps to FULL_FROM_SCRATCH mode (backwards compat)."""
        assert mode_from_string("full-scrape") == ScrapeMode.FULL_FROM_SCRATCH

    def test_mode_from_string_invalid_mode(self):
        """Test invalid mode string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            mode_from_string("invalid_mode")

    def test_mode_from_string_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            mode_from_string("")

    def test_mode_from_string_none_raises_error(self):
        """Test None raises AttributeError (expected behavior)."""
        with pytest.raises(AttributeError):
            mode_from_string(None)


class TestCliModeMapping:
    """
    Tests for CLI mode flag mapping.

    These tests verify that the CLI argument parser correctly
    sets the mode value based on which flag is used.
    """

    def test_all_cli_modes_map_correctly(self):
        """
        Verify all 4 primary CLI mode strings map to correct enums.

        This ensures the CLI flags work as expected:
        - --update -> UPDATE
        - --resume -> RESUME
        - --full-discovery -> FULL_DISCOVERY
        - --full-from-scratch -> FULL_FROM_SCRATCH
        """
        cli_to_enum = {
            "update": ScrapeMode.UPDATE,
            "resume": ScrapeMode.RESUME,
            "full_discovery": ScrapeMode.FULL_DISCOVERY,
            "full_from_scratch": ScrapeMode.FULL_FROM_SCRATCH,
        }

        for cli_string, expected_enum in cli_to_enum.items():
            assert mode_from_string(cli_string) == expected_enum

    def test_backwards_compatible_modes(self):
        """
        Verify backwards compatibility with old mode flags.

        Old flags should still work:
        - --discover -> UPDATE (was incremental discovery)
        - --discover-full -> FULL_DISCOVERY
        """
        # Old discover flag should map to UPDATE
        assert mode_from_string("discover") == ScrapeMode.UPDATE

        # Old discover-full flag should map to FULL_DISCOVERY
        assert mode_from_string("discover-full") == ScrapeMode.FULL_DISCOVERY
