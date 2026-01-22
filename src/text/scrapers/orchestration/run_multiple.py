"""
Pacific Observatory - Multi-Scraper Runner

This module contains all the logic for running multiple newspaper scrapers
in parallel, with intelligent handling of multi-country newspapers.
"""

import subprocess
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import discovery functions from dedicated module
from text.scrapers.orchestration.discovery import discover_configs, group_by_country
from text.scrapers.orchestration.utils import create_progress_display

logger = logging.getLogger(__name__)


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
        mode: Scraping mode - "default", "discover", "discover_full", or "resume"

    Returns:
        Popen object if started, None if dry_run or error
    """
    country = config["country"]
    newspaper = config["newspaper"]

    # Create log directory structure: logs/{country}/{newspaper}/
    log_subdir = log_dir / country / newspaper
    log_subdir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_subdir / f"{timestamp}.log"

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
    if mode == "discover":
        cmd.append("--discover")
    elif mode == "discover_full":
        cmd.append("--discover-full")
    elif mode == "resume":
        cmd.append("--resume")
    # default mode: no flag needed

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


def run_scraper_with_timeout(
    config: Dict[str, str],
    log_dir: Path,
    project_root: Path,
    timeout_seconds: int = 600,
    dry_run: bool = False,
    mode: str = "default",
) -> Dict[str, Any]:
    """
    Run a single scraper with timeout handling.

    This function wraps run_scraper_subprocess and monitors the process,
    killing it if it exceeds the timeout threshold.

    Args:
        config: Configuration dictionary with 'country', 'newspaper', 'config_path'
        log_dir: Base directory for logs
        project_root: Project root directory
        timeout_seconds: Maximum seconds to allow scraper to run (default: 600 = 10 minutes)
        dry_run: If True, print command without executing
        mode: Scraping mode - "default", "discover", "discover_full", or "resume"

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

            return {
                "newspaper": newspaper,
                "country": country,
                "status": status,
                "duration_seconds": duration,
                "log_file": log_file,
                "exit_code": retcode,
            }

        # Check if timeout exceeded
        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            # Write timeout message to log before closing
            if hasattr(process, "log_handle"):
                try:
                    process.log_handle.write(
                        f"\nTIMEOUT: Process killed after {timeout_seconds} seconds\n"
                    )
                    process.log_handle.flush()
                    process.log_handle.close()
                except Exception as e:
                    logger.warning(
                        f"Failed to write timeout message or close log handle: {e}"
                    )

            # Terminate the process
            try:
                process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    # If still running after 1 second, force kill
                    process.kill()
            except Exception as e:
                logger.warning(f"Failed to kill process {country}/{newspaper}: {e}")

            duration = time.time() - start_time
            return {
                "newspaper": newspaper,
                "country": country,
                "status": "timeout",
                "duration_seconds": duration,
                "error_msg": f"Timeout after {timeout_seconds} seconds",
                "log_file": process.log_file if hasattr(process, "log_file") else None,
            }

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


def summarize_results(results: List[Dict[str, any]]):
    """
    Print a compact summary table of scraper results.

    Args:
        results: List of result dictionaries from monitor_processes()
    """
    if not results:
        print("\nNo results to summarize.")
        return

    # Count statuses
    status_counts = defaultdict(int)
    for result in results:
        status_counts[result["status"]] += 1

    # Print header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "─" * 60)
    print(f"SCRAPER SUMMARY ({timestamp})")
    print("─" * 60)

    # Print each result
    for result in sorted(results, key=lambda x: (x["country"], x["newspaper"])):
        status_icon = {
            "success": "✅",
            "warning": "⚠️",
            "failed": "❌",
            "timeout": "⏱️",
        }.get(result["status"], "❓")

        status_text = {
            "success": "Completed successfully",
            "warning": "Completed with warnings",
            "failed": "Failed (see log)",
            "timeout": "Timeout exceeded",
        }.get(result["status"], "Unknown status")

        country = result["country"]
        newspaper = result["newspaper"]

        print(f"{status_icon} {country:20s} / {newspaper:20s} {status_text}")

    # Print totals
    print("─" * 60)
    total = len(results)
    success = status_counts.get("success", 0)
    warnings = status_counts.get("warning", 0)
    failed = status_counts.get("failed", 0)
    timeout = status_counts.get("timeout", 0)

    print(
        f"Total: {total} | Success: {success} | Warnings: {warnings} | Failed: {failed} | Timeout: {timeout}"
    )
    print("─" * 60)


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
        mode: Scraping mode - "default", "discover", "discover_full", or "resume"

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


def run_all_scrapers(
    configs_dir: Path,
    project_root: Path,
    sequential: bool = False,
    dry_run: bool = False,
    mode: str = "default",
    timeout_per_scraper: int = 600,
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
        mode: Scraping mode - "default", "discover", "discover_full", or "resume"
        timeout_per_scraper: Maximum seconds per scraper before timeout (default: 600)

    Returns:
        List of result dictionaries with status information
    """
    print("🌊 Pacific Observatory - Multi-Scraper Runner")
    print("=" * 60)

    # Discover all configurations
    print("\n🔍 Discovering configurations...")
    configs = discover_configs(configs_dir)

    if not configs:
        print("❌ No configurations found.")
        return []

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
            # Normal mode: run all newspapers in this country in parallel using ThreadPoolExecutor
            if not dry_run:
                print(
                    f"\n   🔄 Running {len(country_configs)} scraper(s) in {country} (timeout: {timeout_per_scraper}s)..."
                )

                # Use ThreadPoolExecutor to run scrapers in parallel
                with ThreadPoolExecutor(
                    max_workers=min(len(country_configs), 10)
                ) as executor:
                    # Submit all tasks
                    future_to_config = {
                        executor.submit(
                            run_scraper_with_timeout,
                            config,
                            log_dir,
                            project_root,
                            timeout_per_scraper,
                            dry_run,
                            mode,
                        ): config
                        for config in country_configs
                    }

                    # Collect results as they complete
                    country_results = []
                    for future in as_completed(future_to_config):
                        config = future_to_config[future]
                        try:
                            result = future.result()
                            country_results.append(result)

                            # Print status as each completes
                            status_icon = {
                                "success": "✅",
                                "warning": "⚠️",
                                "failed": "❌",
                                "timeout": "⏱️",
                            }.get(result["status"], "❓")
                            print(
                                f"   {status_icon} {config['country']}/{config['newspaper']} - {result['status']}"
                            )
                        except Exception as e:
                            logger.exception(
                                f"Error running {config['country']}/{config['newspaper']}: {e}"
                            )
                            country_results.append(
                                {
                                    "newspaper": config["newspaper"],
                                    "country": config["country"],
                                    "status": "failed",
                                    "duration_seconds": 0,
                                    "error_msg": str(e),
                                }
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
                    f"   ✓ {country} complete: {success_count} success, {warning_count} warnings, {failed_count} failed, {timeout_count} timeout"
                )
            else:
                # Dry run mode - just print what would be executed
                for config in country_configs:
                    print(f"   [DRY RUN] Would start {config['newspaper']}...")

    # Print final summary
    if not dry_run and all_results:
        summarize_results(all_results)
    elif dry_run:
        print("\n[DRY RUN COMPLETE]")

    # Return list of results
    return all_results
