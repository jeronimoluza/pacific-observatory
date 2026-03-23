"""
Pacific Observatory - Multi-Scraper Runner

This module contains all the logic for running multiple newspaper scrapers
in parallel, with intelligent handling of multi-country newspapers.
"""

import subprocess
import time
import logging
import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from rich.live import Live
from rich.text import Text

# Import discovery functions from dedicated module
from text.scrapers.orchestration.discovery import discover_configs, group_by_country
from text.scrapers.orchestration.utils import create_progress_display
from text.scrapers.orchestration.failure_log import write_failure_log
from text.scrapers.observability import (
    ScraperMetrics,
    print_multi_run_summary,
    save_multi_run_manifest,
    is_scraper_stale,
    read_progress,
    format_duration,
    detect_quality_issues,
    clear_progress_file,
)

logger = logging.getLogger(__name__)


def extract_article_count_from_log(log_file: Path) -> int:
    """
    Extract article count from log file.

    Searches for patterns like:
    - "Scraped 123 articles from"
    - "123 articles scraped"

    Args:
        log_file: Path to log file

    Returns:
        Number of articles scraped, or 0 if extraction fails
    """
    try:
        if not log_file.exists():
            return 0

        log_content = log_file.read_text()

        # Try patterns in order of specificity
        patterns = [
            r"Scraped (\d+) articles from",  # "Scraped 123 articles from"
            r"(\d+) articles scraped",  # "123 articles scraped"
        ]

        for pattern in patterns:
            match = re.search(pattern, log_content)
            if match:
                return int(match.group(1))

        return 0

    except Exception as e:
        logger.warning(f"Failed to extract article count from log: {e}")
        return 0


def run_scraper_subprocess(
    config: Dict[str, str],
    log_dir: Path,
    project_root: Path,
    dry_run: bool = False,
    mode: str = "default",
) -> Optional[subprocess.Popen]:
    """
    Run a single scraper as a subprocess with nohup.

    Args:
        config: Configuration dictionary with 'country', 'newspaper', 'config_path'
        log_dir: Base directory for logs
        project_root: Project root directory
        dry_run: If True, print command without executing
        mode: Scraping mode - "update", "default", "resume", "discover_full", or "full_scrape" (legacy aliases supported)

    Returns:
        Popen object if started, None if dry_run or error
    """
    # Sanitize names to match data folder structure (e.g., "Caixin Global" -> "caixin_global")
    country = _sanitize_name(config["country"])
    newspaper = _sanitize_name(config["newspaper"])

    # Create log directory structure: logs/text/{country}/{newspaper}/execution_logs/
    log_file = Path(
        f"logs/text/{country}/{newspaper}/execution_logs/{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Build command
    # Use poetry run if available, otherwise direct python
    cmd = [
        "poetry",
        "run",
        "python",
        str(project_root / "src" / "text" / "scrapers" / "orchestration" / "main.py"),
        newspaper,
    ]

    # Add mode flag if not default
    # Support both canonical mode names and legacy aliases.
    mode_normalized = mode
    if mode_normalized == "full_discovery":
        mode_normalized = "discover_full"
    elif mode_normalized == "full_from_scratch":
        mode_normalized = "full_scrape"

    if mode_normalized == "update":
        cmd.append("--update")
    elif mode_normalized == "discover_full":
        cmd.append("--full-discovery")
    elif mode_normalized == "resume":
        cmd.append("--resume")
    elif mode_normalized == "full_scrape":
        cmd.append("--full-from-scratch")
    elif mode_normalized in ["default", "discover"]:
        # default mode: no flag needed
        # discover mode isn't exposed as a CLI flag today
        pass
    else:
        raise ValueError(
            "Unknown mode: "
            f"{mode!r}. Supported: update, default, discover, discover_full, resume, full_scrape"
        )

    if dry_run:
        print(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        print(f"          Log file: {log_file}")
        return None

    # Open log file for writing
    log_handle = open(log_file, "w")

    # Start process with nohup-like behavior
    # Use subprocess.Popen with stdout/stderr redirected to log file
    try:
        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            start_new_session=True,  # Detach from parent session (nohup-like)
        )

        # Store metadata on the process object for later reference
        process.log_file = log_file
        process.country = country
        process.newspaper = newspaper
        process.log_handle = log_handle

        return process

    except Exception as e:
        print(f"❌ Failed to start {country}/{newspaper}: {e}")
        log_handle.close()
        return None


def _kill_process_with_timeout(
    process,
    country: str,
    newspaper: str,
    start_time: float,
    reason: str,
) -> Dict[str, Any]:
    """Kill a process and return timeout result."""
    if hasattr(process, "log_handle"):
        try:
            process.log_handle.write(f"\nTIMEOUT: {reason}\n")
            process.log_handle.flush()
            process.log_handle.close()
        except Exception:
            pass

    try:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
    except Exception:
        pass

    return {
        "newspaper": newspaper,
        "country": country,
        "status": "timeout",
        "duration_seconds": time.time() - start_time,
        "error_msg": reason,
        "log_file": getattr(process, "log_file", None),
    }


def run_scraper_with_timeout(
    config: Dict[str, str],
    log_dir: Path,
    project_root: Path,
    timeout_seconds: int = 600,
    dry_run: bool = False,
    mode: str = "default",
) -> Dict[str, Any]:
    """
    Run a single scraper with smart timeout handling.

    This function wraps run_scraper_subprocess and monitors the process,
    using smart timeout logic that only kills scrapers if they're stale
    (no recent activity), rather than killing after N seconds regardless.

    Args:
        config: Configuration dictionary with 'country', 'newspaper', 'config_path'
        log_dir: Base directory for logs
        project_root: Project root directory
        timeout_seconds: Stale timeout - kill if no activity for this many seconds (default: 600)
        dry_run: If True, print command without executing
        mode: Scraping mode - "update", "default", "resume", "discover_full", or "full_scrape" (legacy aliases supported)

    Returns:
        Dictionary with keys:
            - newspaper: str
            - country: str
            - status: str ("success", "failed", "timeout")
            - duration_seconds: float
            - error_msg: str (optional, for failed/timeout cases)
            - log_file: Path (optional)
    """
    country = config["country"]
    newspaper = config["newspaper"]
    start_time = time.time()

    # Clear any stale progress file from previous runs BEFORE starting subprocess
    # This prevents the new subprocess from being considered "stale" immediately
    # due to an old progress file with an outdated last_activity timestamp
    sanitized_country = _sanitize_name(country)
    sanitized_newspaper = _sanitize_name(newspaper)
    clear_progress_file(
        sanitized_country,
        sanitized_newspaper,
        str(project_root / "logs" / "text"),
    )

    # Start the subprocess
    process = run_scraper_subprocess(config, log_dir, project_root, dry_run, mode)

    # If process failed to start
    if process is None:
        duration = time.time() - start_time
        return {
            "newspaper": newspaper,
            "country": country,
            "status": "failed",
            "duration_seconds": duration,
            "error_msg": "Failed to start subprocess",
        }

    # Poll the process until completion or timeout
    while True:
        retcode = process.poll()

        # Process has completed
        if retcode is not None:
            duration = time.time() - start_time

            # Close log handle
            if hasattr(process, "log_handle"):
                process.log_handle.close()

            # Determine status from log file
            log_file = process.log_file
            status = parse_log_status(log_file, retcode)

            # Extract article count if successful
            result = {
                "newspaper": newspaper,
                "country": country,
                "status": status,
                "duration_seconds": duration,
                "log_file": log_file,
                "exit_code": retcode,
            }

            # Add article count for successful runs
            if status == "success":
                articles_scraped = extract_article_count_from_log(log_file)
                result["articles_scraped"] = articles_scraped

            return result

        elapsed = time.time() - start_time

        # Safety net: kill if exceeded max runtime (2 hours)
        max_runtime_seconds = 7200
        if elapsed >= max_runtime_seconds:
            return _kill_process_with_timeout(
                process,
                country,
                newspaper,
                start_time,
                f"Max runtime exceeded ({max_runtime_seconds}s)",
            )

        # Smart timeout: check if scraper is stale (no recent activity)
        if is_scraper_stale(
            country, newspaper, timeout_seconds, project_root / "logs" / "text"
        ):
            return _kill_process_with_timeout(
                process,
                country,
                newspaper,
                start_time,
                f"No activity for {timeout_seconds}s (stale)",
            )

        # Sleep before next poll
        time.sleep(1)


def monitor_processes(
    processes: List[subprocess.Popen],
    check_interval: float = 2.0,
    use_progress: bool = True,
) -> List[Dict[str, Any]]:
    """
    Monitor running processes and report when they complete.

    Args:
        processes: List of Popen objects to monitor
        check_interval: Seconds between status checks
        use_progress: Whether to use Rich progress display

    Returns:
        List of result dictionaries with status information
    """
    results = []
    remaining = list(processes)

    if not use_progress:
        # Legacy mode: simple print statements
        print(f"\n🔄 Monitoring {len(processes)} scraper(s)...\n")

        while remaining:
            for process in remaining[:]:
                retcode = process.poll()

                if retcode is not None:
                    country = process.country
                    newspaper = process.newspaper
                    log_file = process.log_file

                    if hasattr(process, "log_handle"):
                        process.log_handle.close()

                    status = parse_log_status(log_file, retcode)

                    result = {
                        "country": country,
                        "newspaper": newspaper,
                        "log_file": log_file,
                        "exit_code": retcode,
                        "status": status,
                    }
                    results.append(result)

                    status_icon = {
                        "success": "✅",
                        "warning": "⚠️",
                        "failed": "❌",
                    }.get(status, "❓")

                    print(f"{status_icon} {country}/{newspaper} completed ({status})")

                    remaining.remove(process)

            if remaining:
                time.sleep(check_interval)

        return results

    # Rich progress mode
    progress, console = create_progress_display()

    # Create task for each process
    task_map = {}  # process -> task_id

    with progress:
        for process in processes:
            task_id = progress.add_task(
                "[yellow]Running...",
                country=process.country,
                newspaper=process.newspaper,
                total=100,
                completed=0,
            )
            task_map[process] = task_id

        # Monitor processes
        while remaining:
            for process in remaining[:]:
                task_id = task_map[process]
                retcode = process.poll()

                if retcode is not None:
                    # Process finished
                    country = process.country
                    newspaper = process.newspaper
                    log_file = process.log_file

                    if hasattr(process, "log_handle"):
                        process.log_handle.close()

                    status = parse_log_status(log_file, retcode)

                    result = {
                        "country": country,
                        "newspaper": newspaper,
                        "log_file": log_file,
                        "exit_code": retcode,
                        "status": status,
                    }
                    results.append(result)

                    # Update progress with final status
                    if status == "success":
                        progress.update(
                            task_id, description="[green]✅ Completed", completed=100
                        )
                    elif status == "warning":
                        progress.update(
                            task_id,
                            description="[yellow]⚠️  Completed (warnings)",
                            completed=100,
                        )
                    else:
                        progress.update(
                            task_id, description="[red]❌ Failed", completed=100
                        )

                    remaining.remove(process)
                else:
                    # Still running - update progress bar
                    current = progress.tasks[task_id].completed
                    if current < 90:  # Keep it moving but never reach 100 until done
                        progress.update(task_id, completed=min(current + 2, 90))

            if remaining:
                time.sleep(check_interval)

    return results


def parse_log_status(log_file: Path, exit_code: int) -> str:
    """
    Parse log file to determine scraper status.

    Args:
        log_file: Path to log file
        exit_code: Process exit code

    Returns:
        Status string: 'success', 'warning', or 'failed'
    """
    # Failed if non-zero exit code
    if exit_code != 0:
        return "failed"

    # Check log content for warnings or errors
    try:
        if not log_file.exists():
            return "failed"

        log_content = log_file.read_text()

        # Look for warning indicators
        warning_indicators = [
            "WARNING",
            "Warning",
            "Exception",
            "Error:",
            "Failed URLs:",
        ]

        has_warnings = any(indicator in log_content for indicator in warning_indicators)

        # Look for success indicators
        success_indicators = [
            "Scraping completed successfully",
            "✅",
        ]

        has_success = any(indicator in log_content for indicator in success_indicators)

        if has_success and not has_warnings:
            return "success"
        elif has_success and has_warnings:
            return "warning"
        else:
            return "failed"

    except Exception:
        return "failed"


def run_multi_country_group_sequential(
    group: List[Dict[str, str]],
    log_dir: Path,
    project_root: Path,
    dry_run: bool = False,
    mode: str = "default",
) -> List[Dict[str, Any]]:
    """
    Run a multi-country newspaper group sequentially.

    This function runs all countries for a single newspaper sequentially
    to avoid rate limiting and blocking issues.

    Args:
        group: List of config dictionaries for the same newspaper across countries
        log_dir: Base directory for logs
        project_root: Project root directory
        dry_run: If True, print command without executing
        mode: Scraping mode - "default", "update", "resume", "full_discovery", or "full_from_scratch"

    Returns:
        List of result dictionaries
    """
    newspaper_name = group[0]["newspaper"]
    print(f"\n   Group: {newspaper_name} ({len(group)} countries)")

    results = []
    for config in group:
        print(f"      Starting {config['country']}/{config['newspaper']}...")
        process = run_scraper_subprocess(config, log_dir, project_root, dry_run, mode)
        if process:
            # Wait for this scraper to complete before starting the next one
            group_results = monitor_processes([process])
            results.extend(group_results)

    return results


def _sanitize_name(name: str) -> str:
    """
    Sanitize a name for use in filesystem paths.

    Matches CSVStorage._sanitize_name() to ensure consistency.
    """
    import re

    # Replace spaces with underscores and remove special characters
    sanitized = re.sub(r"[^\w\-_.]", "_", name.replace(" ", "_").lower())
    return sanitized.strip("_")


def format_live_status(
    country: str, newspaper: str, project_root: Path, start_time: float
) -> str:
    """
    Format live status line for a running scraper.

    Returns string like: "fiji/fiji_sun     [Discovering]  12 urls found (0m 34s)"
    """
    progress = read_progress(country, newspaper, str(project_root / "logs" / "text"))
    elapsed = time.time() - start_time
    elapsed_str = format_duration(elapsed)

    # Format newspaper name with padding
    name = f"{country}/{newspaper}"
    name_padded = f"{name:<30}"

    if progress is None:
        return f"   {name_padded} [Starting]     (initializing...)"

    phase = progress.get("phase", "unknown")

    if phase == "discovering":
        urls = progress.get("urls_found", 0)
        return f"   {name_padded} [Discovering]  {urls} urls found ({elapsed_str})"
    elif phase == "scraping":
        articles = progress.get("articles_scraped", 0)
        return f"   {name_padded} [Scraping]     {articles} articles ({elapsed_str})"
    elif phase == "completed":
        return f"   {name_padded} [Completed]    ({elapsed_str})"
    elif phase == "failed":
        return f"   {name_padded} [Failed]       ({elapsed_str})"
    else:
        return f"   {name_padded} [{phase}]       ({elapsed_str})"


def format_completion_status(result: Dict[str, Any], project_root: Path) -> str:
    """
    Format completion status for a finished scraper.

    Returns multi-line string like:
       ✓ fiji/fiji_sun - Completed
           14 new articles, 12 new urls, 0 quality warnings
           Time: 2m 34s
    """
    country = result["country"]
    newspaper = result["newspaper"]
    status = result["status"]
    duration = result.get("duration_seconds", 0)

    name = f"{country}/{newspaper}"
    duration_str = format_duration(duration)

    # Get final counts from progress file
    progress = read_progress(country, newspaper, str(project_root / "logs" / "text"))

    articles = 0
    urls = 0
    if progress:
        articles = progress.get("articles_scraped", 0)
        urls = progress.get("urls_found", 0)

    # Get quality warnings count from manifest
    quality_warnings = 0
    manifest_dir = project_root / "logs" / "text" / country / newspaper / "individual"
    if manifest_dir.exists():
        manifest_files = list(manifest_dir.glob("*.json"))
        if manifest_files:
            latest = max(manifest_files, key=lambda p: p.stat().st_mtime)
            try:
                manifest_data = json.loads(latest.read_text())
                metrics = ScraperMetrics.from_dict(manifest_data)
                quality_warnings = len(detect_quality_issues(metrics))
            except Exception:
                pass

    # Format based on status
    if status == "success":
        icon = "✓"
        status_text = "Completed"
    elif status == "warning":
        icon = "⚠"
        status_text = "Completed with warnings"
    elif status == "timeout":
        icon = "⏱"
        status_text = "Timeout"
    else:
        icon = "✗"
        status_text = "Failed"

    lines = [f"   {icon} {name} - {status_text}"]

    if status in ("success", "warning"):
        warning_text = (
            f"{quality_warnings} quality warning{'s' if quality_warnings != 1 else ''}"
        )
        lines.append(f"       {articles} new articles, {urls} new urls, {warning_text}")
    elif status == "timeout":
        lines.append(f"       {result.get('error_msg', 'No activity detected')}")
    elif status == "failed":
        lines.append(f"       {result.get('error_msg', 'Unknown error')}")

    lines.append(f"       Time: {duration_str}")

    return "\n".join(lines)


def collect_run_manifests(
    newspaper_configs: List[Dict[str, str]],
) -> List[ScraperMetrics]:
    """
    Collect run manifests from all newspapers that just ran.

    Args:
        newspaper_configs: List of newspaper config dicts with 'country' and 'newspaper' keys

    Returns:
        List of ScraperMetrics loaded from manifests
    """
    manifests = []

    for config in newspaper_configs:
        # Sanitize names to match actual folder structure (e.g., "Caixin Global" -> "caixin_global")
        country = _sanitize_name(config["country"])
        newspaper = _sanitize_name(config["newspaper"])

        manifest_dir = Path(f"logs/text/{country}/{newspaper}/individual")

        # Skip if no manifests exist yet
        if not manifest_dir.exists():
            logger.warning(f"No manifests found for {newspaper}")
            continue

        # Get most recent manifest
        manifest_files = list(manifest_dir.glob("*.json"))
        if not manifest_files:
            logger.warning(f"No manifest files in {manifest_dir}")
            continue

        latest_manifest = max(manifest_files, key=lambda p: p.stat().st_mtime)

        # Load and parse
        try:
            manifest_data = json.loads(latest_manifest.read_text())
            metrics = ScraperMetrics.from_dict(manifest_data)
            manifests.append(metrics)
        except Exception as e:
            logger.error(f"Failed to load manifest {latest_manifest}: {e}")

    return manifests


def run_country_parallel_with_display(
    configs: List[Dict[str, str]],
    log_dir: Path,
    project_root: Path,
    timeout_seconds: int,
    mode: str,
) -> List[Dict[str, Any]]:
    """
    Run scrapers for a country in parallel with live status display.
    """
    results = []
    running = {}  # newspaper -> (future, start_time, config)
    completed_output = []  # Completion messages to show

    with ThreadPoolExecutor(max_workers=min(len(configs), 10)) as executor:
        # Submit all tasks
        for config in configs:
            future = executor.submit(
                run_scraper_with_timeout,
                config,
                log_dir,
                project_root,
                timeout_seconds,
                False,
                mode,
            )
            running[config["newspaper"]] = (future, time.time(), config)

        # Monitor with live display
        try:
            with Live(refresh_per_second=2) as live:
                while running:
                    # Build display text
                    lines = []

                    # Show completed scrapers first
                    for msg in completed_output:
                        lines.append(msg)

                    if completed_output and running:
                        lines.append("")  # Separator

                    # Show running scrapers
                    for newspaper, (future, start_time, config) in list(
                        running.items()
                    ):
                        if future.done():
                            # Scraper finished
                            try:
                                result = future.result()
                                results.append(result)
                                completed_output.append(
                                    format_completion_status(result, project_root)
                                )
                            except Exception as e:
                                result = {
                                    "newspaper": config["newspaper"],
                                    "country": config["country"],
                                    "status": "failed",
                                    "duration_seconds": time.time() - start_time,
                                    "error_msg": str(e),
                                }
                                results.append(result)
                                completed_output.append(
                                    format_completion_status(result, project_root)
                                )
                            del running[newspaper]
                        else:
                            # Still running - show live status
                            country = _sanitize_name(config["country"])
                            newspaper_san = _sanitize_name(config["newspaper"])
                            status_line = format_live_status(
                                country, newspaper_san, project_root, start_time
                            )
                            lines.append(status_line)

                    live.update(Text("\n".join(lines)))
                    time.sleep(0.5)

            # Print all completed output after the Live context ends
            # This ensures the last newspaper's completion status is displayed
            for msg in completed_output:
                print(msg)

        except Exception:
            # Fallback if Rich fails
            for newspaper, (future, start_time, config) in running.items():
                try:
                    result = future.result(timeout=timeout_seconds)
                    results.append(result)
                except Exception as e:
                    results.append(
                        {
                            "newspaper": config["newspaper"],
                            "country": config["country"],
                            "status": "failed",
                            "error_msg": str(e),
                        }
                    )

    return results


def run_all_scrapers(
    configs_dir: Path,
    project_root: Path,
    sequential: bool = False,
    dry_run: bool = False,
    mode: str = "default",
    timeout_per_scraper: int = 600,
    exclude: Optional[List[str]] = None,
    include: Optional[List[str]] = None,
    exclude_countries: Optional[List[str]] = None,
    country_filter: Optional[str] = None,
) -> List[Dict]:
    """
    Run all newspaper scrapers with country-level sequential execution.

    Loops over countries sequentially, and within each country runs all
    newspapers in parallel. This reduces memory usage compared to running
    all scrapers globally in parallel.

    Args:
        configs_dir: Path to the configs directory
        project_root: Project root directory
        sequential: If True, run all scrapers sequentially (for debugging)
        dry_run: If True, print what would be executed without running
        mode: Scraping mode - "default", "update", "resume", "full_discovery", or "full_from_scratch"
        timeout_per_scraper: Maximum seconds per scraper before timeout (default: 600)
        exclude: List of newspaper names to exclude (case-insensitive)
        include: List of newspaper names to include exclusively (case-insensitive); if None, all are included
        exclude_countries: List of country names to exclude (case-insensitive)

    Returns:
        List of result dictionaries with status information
    """
    print("🌊 Pacific Observatory - Multi-Scraper Runner")
    print("=" * 60)

    # Track run start time for manifest
    multi_run_start_time = datetime.utcnow()

    # Discover all configurations
    print("\n🔍 Discovering configurations...")
    configs = discover_configs(configs_dir)

    if not configs:
        print("❌ No configurations found.")
        return []

    # Filter to a specific country
    if country_filter:
        filtered = [
            c for c in configs if c["country"].lower() == country_filter.lower()
        ]
        if not filtered:
            available = sorted({c["country"] for c in configs})
            print(f"❌ No scrapers found for country: '{country_filter}'")
            print(f"   Available countries: {', '.join(available)}")
            return []
        configs = filtered
        print(f"   Filtering to country: {country_filter}")

    # Filter out excluded countries
    if exclude_countries:
        exclude_country_set = {name.lower() for name in exclude_countries}
        original_count = len(configs)
        configs = [
            c for c in configs if c["country"].lower() not in exclude_country_set
        ]
        excluded_count = original_count - len(configs)
        if excluded_count > 0:
            print(
                "   Excluded "
                f"{excluded_count} scraper(s) from countries: {', '.join(exclude_countries)}"
            )
        if not configs:
            print("❌ No scrapers left after applying country exclusions.")
            return []

    # Filter out excluded scrapers
    if exclude:
        exclude_set = {name.lower() for name in exclude}
        original_count = len(configs)
        configs = [c for c in configs if c["newspaper"].lower() not in exclude_set]
        excluded_count = original_count - len(configs)
        if excluded_count > 0:
            print(f"   Excluded {excluded_count} scraper(s): {', '.join(exclude)}")

    # Filter to only included scrapers
    if include:
        include_set = {name.lower() for name in include}
        configs = [c for c in configs if c["newspaper"].lower() in include_set]
        print(f"   Filtering to: {', '.join(include)}")

    print(f"   Found {len(configs)} scraper configuration(s)")

    # Group by country for sequential country processing
    configs_by_country = group_by_country(configs)
    countries = sorted(configs_by_country.keys())

    print(f"   - {len(countries)} countries")
    for country in countries:
        print(f"      • {country}: {len(configs_by_country[country])} newspaper(s)")

    # Set up log directory
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    if dry_run:
        print("\n[DRY RUN MODE - No scrapers will actually run]\n")

    all_results = []

    # Process each country sequentially
    for country_idx, country in enumerate(countries, 1):
        country_configs = configs_by_country[country]
        print(f"\n{'─' * 60}")
        print(
            f"🌍 [{country_idx}/{len(countries)}] Processing {country} ({len(country_configs)} newspaper(s))"
        )
        print(f"{'─' * 60}")

        if sequential:
            # Debug mode: run all newspapers in this country sequentially
            for config in country_configs:
                print(f"   Starting {config['country']}/{config['newspaper']}...")
                if not dry_run:
                    result = run_scraper_with_timeout(
                        config,
                        log_dir,
                        project_root,
                        timeout_per_scraper,
                        dry_run,
                        mode,
                    )
                    all_results.append(result)
        else:
            # Parallel mode with live display
            if not dry_run:
                print(
                    f"\n   🔄 Running {len(country_configs)} scraper(s) in {country} (timeout: {timeout_per_scraper}s)..."
                )

                country_results = run_country_parallel_with_display(
                    country_configs,
                    log_dir,
                    project_root,
                    timeout_per_scraper,
                    mode,
                )
                all_results.extend(country_results)

                # Print country summary
                success_count = sum(
                    1 for r in country_results if r["status"] == "success"
                )
                warning_count = sum(
                    1 for r in country_results if r["status"] == "warning"
                )
                failed_count = sum(
                    1 for r in country_results if r["status"] == "failed"
                )
                timeout_count = sum(
                    1 for r in country_results if r["status"] == "timeout"
                )
                print(
                    f"\n   ✓ {country} complete: {success_count} success, {warning_count} warnings, {failed_count} failed, {timeout_count} timeout"
                )
            else:
                # Dry run mode - just print what would be executed
                for config in country_configs:
                    print(f"   [DRY RUN] Would start {config['newspaper']}...")

    # Print final summary
    if not dry_run and all_results:
        # Write failure log
        failure_log_path = project_root / "data" / "text" / "last_run_failures.json"
        write_failure_log(all_results, failure_log_path)

        # Notify user if failures occurred
        failures = [r for r in all_results if r.get("status") in ["failed", "timeout"]]
        if failures:
            print(f"\n📝 Failure details saved to: {failure_log_path}")
    elif dry_run:
        print("\n[DRY RUN COMPLETE]")

    # Collect manifests and print multi-run summary
    if not dry_run and all_results:
        logger.info("Collecting run manifests...")
        all_metrics = collect_run_manifests(configs)

        # Print aggregate summary
        print_multi_run_summary(all_metrics)

        # Save multi-run manifest
        completed_at = datetime.utcnow()
        manifest_path = save_multi_run_manifest(
            all_metrics, multi_run_start_time, completed_at
        )
        print(f"Run details: {manifest_path}")

    # Return list of results
    return all_results
