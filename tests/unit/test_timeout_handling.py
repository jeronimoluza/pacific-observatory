"""Unit tests for timeout handling in scraper orchestration."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.orchestration.run_multiple import run_scraper_with_timeout


class TestRunScraperWithTimeout:
    """Tests for run_scraper_with_timeout function."""

    @patch("text.scrapers.orchestration.run_multiple.run_scraper_subprocess")
    @patch("time.time")
    @patch("time.sleep")
    def test_subprocess_timeout_kills_hanging_scraper(
        self, mock_sleep, mock_time, mock_run_subprocess
    ):
        """Test that a hanging process gets killed after timeout."""
        # Mock a hanging process that never completes
        mock_process = Mock()
        mock_process.poll.return_value = None  # Always returns None (still running)
        mock_process.country = "solomon_islands"
        mock_process.newspaper = "sibc"
        mock_process.log_handle = Mock()

        mock_run_subprocess.return_value = mock_process

        # Mock time.time() to simulate timeout
        # Start at 0, then jump past timeout threshold
        # Need: start_time, elapsed check, final duration calc
        mock_time.side_effect = [
            0,
            601,
            602,
        ]  # Start, elapsed check (timeout!), final duration

        # Test config
        config = {
            "country": "solomon_islands",
            "newspaper": "sibc",
            "config_path": "/fake/path",
        }
        log_dir = Path("/fake/logs")
        project_root = Path("/fake/project")
        timeout_seconds = 600

        # Execute
        result = run_scraper_with_timeout(
            config=config,
            log_dir=log_dir,
            project_root=project_root,
            timeout_seconds=timeout_seconds,
            dry_run=False,
            mode="default",
        )

        # Verify process was started
        mock_run_subprocess.assert_called_once_with(
            config, log_dir, project_root, False, "default"
        )

        # Verify log handle was closed before killing
        mock_process.log_handle.close.assert_called_once()

        # Verify process was terminated
        mock_process.terminate.assert_called_once()

        # Verify result indicates timeout
        assert result["status"] == "timeout"
        assert result["newspaper"] == "sibc"
        assert result["country"] == "solomon_islands"
        assert "duration_seconds" in result
        assert result["duration_seconds"] >= timeout_seconds

    @patch("text.scrapers.orchestration.run_multiple.run_scraper_subprocess")
    @patch("time.time")
    @patch("time.sleep")
    def test_subprocess_success_within_timeout(
        self, mock_sleep, mock_time, mock_run_subprocess
    ):
        """Test that a successful process returns success before timeout."""
        # Mock a process that completes successfully
        mock_process = Mock()
        # First two polls return None (running), third returns 0 (success)
        mock_process.poll.side_effect = [None, 0]
        mock_process.country = "solomon_islands"
        mock_process.newspaper = "sibc"
        mock_process.log_handle = Mock()
        mock_process.log_file = Path("/fake/logs/solomon_islands/sibc/test.log")

        mock_run_subprocess.return_value = mock_process

        # Mock time.time() to simulate successful completion
        mock_time.side_effect = [0, 1, 2]  # Start, first poll, second poll (completed)

        # Test config
        config = {
            "country": "solomon_islands",
            "newspaper": "sibc",
            "config_path": "/fake/path",
        }
        log_dir = Path("/fake/logs")
        project_root = Path("/fake/project")
        timeout_seconds = 600

        # Mock parse_log_status to return success
        with patch(
            "text.scrapers.orchestration.run_multiple.parse_log_status"
        ) as mock_parse:
            mock_parse.return_value = "success"

            # Execute
            result = run_scraper_with_timeout(
                config=config,
                log_dir=log_dir,
                project_root=project_root,
                timeout_seconds=timeout_seconds,
                dry_run=False,
                mode="default",
            )

        # Verify process was started
        mock_run_subprocess.assert_called_once()

        # Verify log handle was closed
        mock_process.log_handle.close.assert_called_once()

        # Verify process was NOT terminated (completed normally)
        mock_process.terminate.assert_not_called()

        # Verify result indicates success
        assert result["status"] == "success"
        assert result["newspaper"] == "sibc"
        assert result["country"] == "solomon_islands"
        assert "duration_seconds" in result
        assert result["duration_seconds"] < timeout_seconds

    @patch("text.scrapers.orchestration.run_multiple.run_scraper_subprocess")
    def test_handles_none_process(self, mock_run_subprocess):
        """Test handling when subprocess fails to start."""
        # Mock subprocess returning None (failed to start)
        mock_run_subprocess.return_value = None

        config = {
            "country": "solomon_islands",
            "newspaper": "sibc",
            "config_path": "/fake/path",
        }
        log_dir = Path("/fake/logs")
        project_root = Path("/fake/project")

        # Execute
        result = run_scraper_with_timeout(
            config=config,
            log_dir=log_dir,
            project_root=project_root,
            timeout_seconds=600,
            dry_run=False,
            mode="default",
        )

        # Verify result indicates failure
        assert result["status"] == "failed"
        assert result["newspaper"] == "sibc"
        assert result["country"] == "solomon_islands"
        assert "error_msg" in result
        assert "Failed to start" in result["error_msg"]
