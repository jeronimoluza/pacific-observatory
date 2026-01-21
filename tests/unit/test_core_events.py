"""Unit tests for the event emission system."""

from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.core.events import (
    ScrapeEvent,
    EventEmitter,
    LoggingHandler,
    ConsoleProgressHandler,
    get_emitter,
    set_emitter,
)


class TestScrapeEvent:
    """Tests for the ScrapeEvent dataclass."""

    def test_creates_event_with_required_fields(self):
        """ScrapeEvent should be created with required fields."""
        event = ScrapeEvent(
            event_type="run_started",
            newspaper="fiji_sun",
            country="fiji",
            run_id="abc123",
        )
        assert event.event_type == "run_started"
        assert event.newspaper == "fiji_sun"
        assert event.country == "fiji"
        assert event.run_id == "abc123"

    def test_auto_generates_timestamp(self):
        """ScrapeEvent should auto-generate timestamp."""
        event = ScrapeEvent(
            event_type="run_started",
            newspaper="fiji_sun",
            country="fiji",
            run_id="abc123",
        )
        assert isinstance(event.timestamp, datetime)

    def test_accepts_details_dict(self):
        """ScrapeEvent should accept details dictionary."""
        event = ScrapeEvent(
            event_type="article_scraped",
            newspaper="fiji_sun",
            country="fiji",
            run_id="abc123",
            details={"url": "https://example.com", "title": "Test"},
        )
        assert event.details["url"] == "https://example.com"
        assert event.details["title"] == "Test"

    def test_to_dict_serializes_correctly(self):
        """ScrapeEvent.to_dict should serialize all fields."""
        event = ScrapeEvent(
            event_type="run_started",
            newspaper="fiji_sun",
            country="fiji",
            run_id="abc123",
            details={"mode": "update"},
        )
        data = event.to_dict()

        assert data["event_type"] == "run_started"
        assert data["newspaper"] == "fiji_sun"
        assert data["country"] == "fiji"
        assert data["run_id"] == "abc123"
        assert data["details"]["mode"] == "update"
        assert isinstance(data["timestamp"], str)


class TestEventEmitter:
    """Tests for the EventEmitter class."""

    def test_registers_handler(self):
        """EventEmitter should register handlers."""
        emitter = EventEmitter()
        handler_called = []

        def handler(event):
            handler_called.append(event)

        emitter.on("test_event", handler)

        event = ScrapeEvent(
            event_type="test_event",
            newspaper="test",
            country="test",
            run_id="test",
        )
        emitter.emit(event)

        assert len(handler_called) == 1
        assert handler_called[0] == event

    def test_calls_multiple_handlers(self):
        """EventEmitter should call all registered handlers."""
        emitter = EventEmitter()
        calls = []

        emitter.on("test", lambda e: calls.append("handler1"))
        emitter.on("test", lambda e: calls.append("handler2"))

        event = ScrapeEvent(
            event_type="test",
            newspaper="test",
            country="test",
            run_id="test",
        )
        emitter.emit(event)

        assert calls == ["handler1", "handler2"]

    def test_wildcard_handler_receives_all_events(self):
        """EventEmitter should call wildcard handlers for all events."""
        emitter = EventEmitter()
        events = []

        emitter.on("*", lambda e: events.append(e.event_type))

        for event_type in ["run_started", "article_scraped", "run_completed"]:
            emitter.emit(
                ScrapeEvent(
                    event_type=event_type,
                    newspaper="test",
                    country="test",
                    run_id="test",
                )
            )

        assert events == ["run_started", "article_scraped", "run_completed"]

    def test_handler_exception_does_not_stop_others(self):
        """EventEmitter should continue calling handlers after exception."""
        emitter = EventEmitter()
        calls = []

        def failing_handler(e):
            raise ValueError("Handler error")

        emitter.on("test", failing_handler)
        emitter.on("test", lambda e: calls.append("success"))

        event = ScrapeEvent(
            event_type="test",
            newspaper="test",
            country="test",
            run_id="test",
        )
        emitter.emit(event)

        assert "success" in calls

    def test_off_removes_handler(self):
        """EventEmitter.off should remove a handler."""
        emitter = EventEmitter()
        calls = []

        def handler(e):
            calls.append("called")

        emitter.on("test", handler)
        emitter.off("test", handler)

        emitter.emit(
            ScrapeEvent(
                event_type="test",
                newspaper="test",
                country="test",
                run_id="test",
            )
        )

        assert calls == []

    def test_off_without_handler_removes_all(self):
        """EventEmitter.off without handler should remove all handlers."""
        emitter = EventEmitter()
        calls = []

        emitter.on("test", lambda e: calls.append("h1"))
        emitter.on("test", lambda e: calls.append("h2"))
        emitter.off("test")

        emitter.emit(
            ScrapeEvent(
                event_type="test",
                newspaper="test",
                country="test",
                run_id="test",
            )
        )

        assert calls == []

    def test_disable_prevents_emission(self):
        """EventEmitter.disable should prevent event emission."""
        emitter = EventEmitter()
        calls = []

        emitter.on("test", lambda e: calls.append("called"))
        emitter.disable()

        emitter.emit(
            ScrapeEvent(
                event_type="test",
                newspaper="test",
                country="test",
                run_id="test",
            )
        )

        assert calls == []

    def test_enable_restores_emission(self):
        """EventEmitter.enable should restore event emission."""
        emitter = EventEmitter()
        calls = []

        emitter.on("test", lambda e: calls.append("called"))
        emitter.disable()
        emitter.enable()

        emitter.emit(
            ScrapeEvent(
                event_type="test",
                newspaper="test",
                country="test",
                run_id="test",
            )
        )

        assert calls == ["called"]

    def test_clear_removes_all_handlers(self):
        """EventEmitter.clear should remove all handlers."""
        emitter = EventEmitter()
        calls = []

        emitter.on("test1", lambda e: calls.append("t1"))
        emitter.on("test2", lambda e: calls.append("t2"))
        emitter.on("*", lambda e: calls.append("all"))
        emitter.clear()

        for event_type in ["test1", "test2", "other"]:
            emitter.emit(
                ScrapeEvent(
                    event_type=event_type,
                    newspaper="test",
                    country="test",
                    run_id="test",
                )
            )

        assert calls == []

    def test_chaining_on_calls(self):
        """EventEmitter.on should return self for chaining."""
        emitter = EventEmitter()
        result = emitter.on("test", lambda e: None)
        assert result is emitter


class TestLoggingHandler:
    """Tests for the LoggingHandler class."""

    def test_logs_events(self, caplog):
        """LoggingHandler should log events."""
        import logging

        handler = LoggingHandler(log_level=logging.INFO)

        with caplog.at_level(logging.INFO, logger="text"):
            handler(
                ScrapeEvent(
                    event_type="run_started",
                    newspaper="fiji_sun",
                    country="fiji",
                    run_id="abc123",
                )
            )

        assert "run_started" in caplog.text
        assert "fiji_sun" in caplog.text


class TestConsoleProgressHandler:
    """Tests for the ConsoleProgressHandler class."""

    def test_tracks_article_counts(self, capsys):
        """ConsoleProgressHandler should track article counts."""
        handler = ConsoleProgressHandler()

        # Simulate events
        handler(
            ScrapeEvent(
                event_type="run_started",
                newspaper="fiji_sun",
                country="fiji",
                run_id="abc123",
            )
        )

        for _ in range(5):
            handler(
                ScrapeEvent(
                    event_type="article_scraped",
                    newspaper="fiji_sun",
                    country="fiji",
                    run_id="abc123",
                )
            )

        handler(
            ScrapeEvent(
                event_type="run_completed",
                newspaper="fiji_sun",
                country="fiji",
                run_id="abc123",
                details={"status": "success", "duration_seconds": 10.5},
            )
        )

        output = capsys.readouterr().out
        assert "fiji_sun" in output
        assert "Completed: SUCCESS" in output


class TestGlobalEmitter:
    """Tests for the global emitter functions."""

    def test_get_emitter_returns_same_instance(self):
        """get_emitter should return the same instance."""
        emitter1 = get_emitter()
        emitter2 = get_emitter()
        assert emitter1 is emitter2

    def test_set_emitter_changes_global(self):
        """set_emitter should change the global emitter."""
        original = get_emitter()
        new_emitter = EventEmitter()

        set_emitter(new_emitter)
        assert get_emitter() is new_emitter

        # Restore original
        set_emitter(original)
