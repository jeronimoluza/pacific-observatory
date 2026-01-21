"""
Configuration validation CLI for newspaper scrapers.

Validates YAML configuration files against the schema and optionally
tests connectivity to the target website.

Usage:
    python -m text.scrapers.orchestration.validate path/to/config.yaml
    python -m text.scrapers.orchestration.validate path/to/config.yaml --live
    python -m text.scrapers.orchestration.validate --all
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple
import yaml

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def validate_schema(config: dict, config_path: Path) -> List[Tuple[str, str]]:
    """
    Validate config against the schema.

    Returns list of (level, message) tuples where level is 'error' or 'warning'.
    """
    issues = []

    # Required fields
    required_fields = ["name", "country", "base_url"]
    for field in required_fields:
        if field not in config:
            issues.append(("error", f"Missing required field: {field}"))

    # Validate name matches filename (allowing for spaces vs underscores)
    if "name" in config:
        expected_name = config_path.stem
        normalized_config_name = (
            config["name"].lower().replace(" ", "_").replace("-", "_").replace("'", "")
        )
        normalized_expected = expected_name.lower().replace("-", "_")
        if normalized_config_name != normalized_expected:
            issues.append(
                (
                    "warning",
                    f"Config name '{config['name']}' doesn't match filename '{expected_name}'",
                )
            )

    # Validate base_url format
    if "base_url" in config:
        base_url = config["base_url"]
        if not base_url.startswith(("http://", "https://")):
            issues.append(("error", "base_url must start with http:// or https://"))
        if base_url.endswith("/"):
            issues.append(("warning", "base_url should not end with a trailing slash"))

    # Validate client type
    if "client" in config:
        valid_clients = ["http", "browser"]
        if config["client"] not in valid_clients:
            issues.append(
                (
                    "error",
                    f"Invalid client type: {config['client']}. Must be one of: {valid_clients}",
                )
            )

    # Validate listing config
    if "listing" in config:
        listing = config["listing"]
        if "type" not in listing:
            issues.append(("error", "listing.type is required"))
        else:
            valid_types = [
                "pagination",
                "archive",
                "search",
                "category",
                "api",
                "paginated_archive",
                "follow_link",
                "rss",
            ]
            if listing["type"] not in valid_types:
                issues.append(
                    (
                        "error",
                        f"Invalid listing type: {listing['type']}. Must be one of: {valid_types}",
                    )
                )

        if "start_url" not in listing and listing.get("type") != "api":
            issues.append(("warning", "listing.start_url is typically required"))

    # Validate selectors config (used for HTML scraping)
    # Note: API-based scrapers may use json_paths in listing config instead
    if "selectors" in config:
        selectors = config["selectors"]
        if "thumbnail" in selectors:
            thumbnail = selectors["thumbnail"]
            if "container" not in thumbnail:
                issues.append(
                    ("warning", "selectors.thumbnail.container is recommended")
                )
        if "article" in selectors:
            article = selectors["article"]
            if "body" not in article:
                issues.append(("warning", "selectors.article.body is recommended"))
    elif "listing" in config and config["listing"].get("type") != "api":
        # Non-API scrapers should have selectors
        issues.append(
            ("warning", "selectors configuration is recommended for non-API scrapers")
        )

    # Validate cleaning functions
    if "cleaning" in config:
        from text.scrapers.pipelines.cleaning import CLEANING_FUNCTIONS

        for field, func_name in config["cleaning"].items():
            if func_name and func_name not in CLEANING_FUNCTIONS:
                issues.append(
                    (
                        "warning",
                        f"Cleaning function '{func_name}' not found in registry",
                    )
                )

    # Validate numeric fields
    if "concurrency" in config:
        if not isinstance(config["concurrency"], int) or config["concurrency"] < 1:
            issues.append(("error", "concurrency must be a positive integer"))

    if "rate_limit" in config:
        if (
            not isinstance(config["rate_limit"], (int, float))
            or config["rate_limit"] < 0
        ):
            issues.append(("error", "rate_limit must be a non-negative number"))

    return issues


def validate_connectivity(config: dict) -> List[Tuple[str, str]]:
    """
    Test connectivity to the target website.

    Returns list of (level, message) tuples.
    """
    import httpx

    issues = []
    base_url = config.get("base_url", "")

    if not base_url:
        return [("error", "Cannot test connectivity without base_url")]

    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(base_url)

            if response.status_code == 200:
                issues.append(("info", "Base URL accessible (200 OK)"))
            elif response.status_code in (301, 302):
                issues.append(
                    (
                        "warning",
                        f"Base URL redirects to {response.headers.get('Location')}",
                    )
                )
            elif response.status_code == 403:
                issues.append(
                    ("warning", "Base URL returns 403 Forbidden - may need auth config")
                )
            elif response.status_code == 404:
                issues.append(("error", "Base URL returns 404 Not Found"))
            else:
                issues.append(
                    ("warning", f"Base URL returns status {response.status_code}")
                )

    except httpx.ConnectError:
        issues.append(("error", f"Cannot connect to {base_url}"))
    except httpx.TimeoutException:
        issues.append(("warning", f"Connection to {base_url} timed out"))
    except Exception as e:
        issues.append(("error", f"Error connecting to {base_url}: {e}"))

    # Test listing URL if configured
    if "listing" in config and "start_url" in config["listing"]:
        listing_url = base_url.rstrip("/") + config["listing"]["start_url"]
        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(listing_url)
                if response.status_code == 200:
                    issues.append(("info", "Listing URL accessible (200 OK)"))
                else:
                    issues.append(
                        (
                            "warning",
                            f"Listing URL returns status {response.status_code}",
                        )
                    )
        except Exception as e:
            issues.append(("warning", f"Error accessing listing URL: {e}"))

    return issues


def format_result(level: str, message: str) -> str:
    """Format a validation result for display."""
    symbols = {
        "error": "X",
        "warning": "!",
        "info": "+",
    }
    symbol = symbols.get(level, "?")
    return f"[{symbol}] {message}"


def validate_config(config_path: Path, live: bool = False) -> bool:
    """
    Validate a single config file.

    Returns True if validation passed (no errors).
    """
    print(f"\nValidating: {config_path}")
    print("-" * 50)

    # Load config
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(format_result("error", f"Failed to parse YAML: {e}"))
        return False

    if not config:
        print(format_result("error", "Config file is empty"))
        return False

    # Schema validation
    issues = validate_schema(config, config_path)

    # Live connectivity test
    if live:
        issues.extend(validate_connectivity(config))

    # Display results
    errors = 0
    warnings = 0

    for level, message in issues:
        print(format_result(level, message))
        if level == "error":
            errors += 1
        elif level == "warning":
            warnings += 1

    # Summary
    print()
    if errors == 0 and warnings == 0:
        print("Validation passed!")
    else:
        print(f"Validation complete: {errors} error(s), {warnings} warning(s)")

    return errors == 0


def main():
    """Main entry point for the validation CLI."""
    parser = argparse.ArgumentParser(
        description="Validate newspaper scraper configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s configs/fiji/fiji_sun.yaml          # Validate single file
  %(prog)s configs/fiji/fiji_sun.yaml --live   # With connectivity test
  %(prog)s --all                               # Validate all configs
  %(prog)s --all --live                        # All configs with connectivity
        """,
    )

    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        help="Path to the configuration file to validate",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Test connectivity to the target website",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all configuration files",
    )

    parser.add_argument(
        "--configs-dir",
        type=Path,
        default=Path(__file__).parent.parent / "configs",
        help="Directory containing config files (default: src/text/scrapers/configs)",
    )

    args = parser.parse_args()

    if args.all:
        # Validate all configs
        configs_dir = args.configs_dir
        if not configs_dir.exists():
            print(f"Error: Configs directory not found: {configs_dir}")
            sys.exit(1)

        config_files = list(configs_dir.rglob("*.yaml"))
        config_files = [c for c in config_files if c.name != "template.yaml"]

        if not config_files:
            print(f"No config files found in {configs_dir}")
            sys.exit(1)

        print(f"Validating {len(config_files)} configuration files...")

        passed = 0
        failed = 0

        for config_path in sorted(config_files):
            if validate_config(config_path, live=args.live):
                passed += 1
            else:
                failed += 1

        print("\n" + "=" * 50)
        print(f"Summary: {passed} passed, {failed} failed")

        sys.exit(0 if failed == 0 else 1)

    elif args.config:
        # Validate single config
        if not args.config.exists():
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)

        success = validate_config(args.config, live=args.live)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
