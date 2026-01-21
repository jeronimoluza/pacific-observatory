"""Unit tests for the logging configuration module."""

import json
import logging
from pathlib import Path
import tempfile

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.core.logging_config import (
    configure_logging,
    get_logger,
    LogContext,
    JSONFormatter,
    ConsoleFormatter,
    LoggingMixin,
    get_correlation_context,
)


class TestLogContext:
    """Tests for the LogContext context manager."""

    def test_sets_correlation_context(self):
        """LogContext should set correlation context variables."""
        with LogContext(run_id="test123", newspaper="fiji_sun"):
            ctx = get_correlation_context()
            assert ctx["run_id"] == "test123"
            assert ctx["newspaper"] == "fiji_sun"

    def test_restores_context_on_exit(self):
        """LogContext should restore context on exit."""
        with LogContext(run_id="outer"):
            assert get_correlation_context()["run_id"] == "outer"

            with LogContext(run_id="inner"):
                assert get_correlation_context()["run_id"] == "inner"

            assert get_correlation_context()["run_id"] == "outer"

    def test_generates_run_id_if_missing(self):
        """LogContext should generate a run_id if not provided."""
        with LogContext(newspaper="fiji_sun"):
            ctx = get_correlation_context()
            assert "run_id" in ctx
            assert len(ctx["run_id"]) == 8

    def test_includes_extra_context(self):
        """LogContext should include extra context fields."""
        with LogContext(newspaper="fiji_sun", extra={"batch": 5}):
            ctx = get_correlation_context()
            assert ctx["batch"] == 5

    def test_omits_none_values(self):
        """LogContext should not include None values."""
        with LogContext(newspaper=None, country=None):
            ctx = get_correlation_context()
            assert "newspaper" not in ctx
            assert "country" not in ctx


class TestJSONFormatter:
    """Tests for the JSON log formatter."""

    def test_formats_as_json(self):
        """JSONFormatter should output valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_includes_correlation_context(self):
        """JSONFormatter should include correlation context."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with LogContext(run_id="abc123", newspaper="fiji_sun"):
            output = formatter.format(record)
            data = json.loads(output)

        assert "correlation" in data
        assert data["correlation"]["run_id"] == "abc123"
        assert data["correlation"]["newspaper"] == "fiji_sun"

    def test_includes_extra_fields(self):
        """JSONFormatter should include extra record fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.url = "https://example.com"
        record.status_code = 200

        output = formatter.format(record)
        data = json.loads(output)

        assert "extra" in data
        assert data["extra"]["url"] == "https://example.com"
        assert data["extra"]["status_code"] == 200


class TestConsoleFormatter:
    """Tests for the console log formatter."""

    def test_formats_readable_output(self):
        """ConsoleFormatter should output human-readable format."""
        formatter = ConsoleFormatter(use_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)

        assert "INFO" in output
        assert "Test message" in output

    def test_includes_context_in_output(self):
        """ConsoleFormatter should include context in output."""
        formatter = ConsoleFormatter(use_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with LogContext(newspaper="fiji_sun", run_id="abc12345"):
            output = formatter.format(record)

        assert "fiji_sun" in output
        assert "abc12345" in output


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_returns_logger_with_text_prefix(self):
        """get_logger should return logger under text namespace."""
        logger = get_logger("mymodule")
        assert logger.name == "text.mymodule"

    def test_preserves_text_prefix(self):
        """get_logger should not duplicate text prefix."""
        logger = get_logger("text.scrapers.client")
        assert logger.name == "text.scrapers.client"


class TestLoggingMixin:
    """Tests for the LoggingMixin class."""

    def test_provides_logger_attribute(self):
        """LoggingMixin should provide a logger attribute."""

        class TestClass(LoggingMixin):
            pass

        obj = TestClass()
        assert hasattr(obj, "logger")
        assert isinstance(obj.logger, logging.Logger)


class TestConfigureLogging:
    """Tests for the configure_logging function."""

    def test_creates_log_directory(self):
        """configure_logging should create the log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            configure_logging(
                log_dir=log_dir,
                enable_console=False,
                enable_file=True,
            )
            assert log_dir.exists()

    def test_respects_log_level(self):
        """configure_logging should set the correct log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            configure_logging(
                log_level="DEBUG",
                log_dir=Path(tmpdir),
                enable_console=True,
                enable_file=False,
            )
            logger = logging.getLogger("text")
            assert logger.level == logging.DEBUG
