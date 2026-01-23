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
from typing import Any, Dict, List, Tuple
import yaml
import httpx
from bs4 import BeautifulSoup

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def validate_yaml_syntax(config_path: Path) -> Dict[str, Any]:
    """
    Validate YAML file syntax.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with:
        - valid (bool): Whether YAML is valid
        - errors (list): List of error messages
        - config (dict): Parsed config if valid
    """
    errors = []
    config = None

    try:
        if not config_path.exists():
            errors.append(f"File not found: {config_path}")
            return {"valid": False, "errors": errors}

        with open(config_path) as f:
            config = yaml.safe_load(f)

        if config is None:
            errors.append("Config file is empty")
            return {"valid": False, "errors": errors}

    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error: {e}")
        return {"valid": False, "errors": errors}
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return {"valid": False, "errors": errors}

    return {"valid": True, "errors": [], "config": config}


def validate_required_fields(config: Dict) -> Dict[str, Any]:
    """
    Check for required fields in configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary with:
        - valid (bool): Whether all required fields are present
        - errors (list): List of missing field errors
    """
    errors = []
    required_fields = ["name", "country", "base_url", "listing", "selectors"]

    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")

    return {"valid": len(errors) == 0, "errors": errors}


def validate_url_reachable(url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Test if URL is reachable.

    Args:
        url: URL to test
        timeout: Request timeout in seconds

    Returns:
        Dictionary with:
        - reachable (bool): Whether URL is accessible
        - status_code (int): HTTP status code if reachable
        - error (str): Error message if not reachable
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)

            if response.status_code == 200:
                return {
                    "reachable": True,
                    "status_code": response.status_code,
                    "error": None,
                }
            else:
                return {
                    "reachable": False,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                }

    except httpx.ConnectError as e:
        return {
            "reachable": False,
            "status_code": None,
            "error": f"Connection error: {str(e)}",
        }
    except httpx.TimeoutException as e:
        return {
            "reachable": False,
            "status_code": None,
            "error": f"Timeout error: {str(e)}",
        }
    except Exception as e:
        return {
            "reachable": False,
            "status_code": None,
            "error": f"Error: {str(e)}",
        }


def validate_selectors_find_content(config: Dict, sample_url: str) -> Dict[str, Any]:
    """
    Test if selectors can find content on a sample page.

    Args:
        config: Configuration dictionary with selectors
        sample_url: URL to test selectors against

    Returns:
        Dictionary with:
        - valid (bool): Whether selectors found content
        - found_count (int): Number of elements found
        - selector (str): Selector that was tested
        - error (str): Error message if validation failed
    """
    # Check if config has selectors
    if "selectors" not in config:
        return {
            "valid": False,
            "found_count": 0,
            "selector": None,
            "error": "No selectors found in config",
        }

    # Get thumbnail container selector
    thumbnail_selectors = config["selectors"].get("thumbnail", {})
    container_selector = thumbnail_selectors.get("container")

    if not container_selector:
        return {
            "valid": False,
            "found_count": 0,
            "selector": None,
            "error": "No thumbnail container selector found",
        }

    # Try to fetch the page and find elements
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(sample_url)

            if response.status_code != 200:
                return {
                    "valid": False,
                    "found_count": 0,
                    "selector": container_selector,
                    "error": f"Page returned status {response.status_code}",
                }

            # Parse HTML and find elements
            soup = BeautifulSoup(response.text, "html.parser")
            elements = soup.select(container_selector)

            return {
                "valid": len(elements) > 0,
                "found_count": len(elements),
                "selector": container_selector,
                "error": None
                if len(elements) > 0
                else "No elements found with selector",
            }

    except Exception as e:
        return {
            "valid": False,
            "found_count": 0,
            "selector": container_selector,
            "error": f"Error fetching page: {str(e)}",
        }


def validate_config_comprehensive(config_path: Path) -> Dict[str, Any]:
    """
    Run comprehensive validation checks on a configuration file.

    Args:
        config_path: Path to configuration file

    Returns:
        Dictionary with:
        - overall_valid (bool): Whether all validations passed
        - sections (dict): Results from each validation section
    """
    sections = {}
    overall_valid = True

    # 1. Validate YAML syntax
    syntax_result = validate_yaml_syntax(config_path)
    sections["syntax"] = syntax_result

    if not syntax_result["valid"]:
        overall_valid = False
        # If syntax is invalid, we can't proceed with other checks
        return {
            "overall_valid": False,
            "sections": sections,
        }

    config = syntax_result["config"]

    # 2. Validate required fields
    fields_result = validate_required_fields(config)
    sections["required_fields"] = fields_result

    if not fields_result["valid"]:
        overall_valid = False

    # 3. Validate base URL reachability (optional check - doesn't fail overall)
    if "base_url" in config:
        url_result = validate_url_reachable(config["base_url"])
        sections["base_url"] = url_result
        # Note: URL unreachability is a warning, not a failure

    # 4. Check cleaning functions
    warnings = []
    if "cleaning" in config:
        try:
            from text.scrapers.pipelines.cleaning import get_cleaning_func

            for field_name, func_name in config["cleaning"].items():
                if func_name:
                    try:
                        cleaning_func = get_cleaning_func(func_name)
                        if cleaning_func is None:
                            warnings.append(
                                f"Cleaning function '{func_name}' not found (will use defaults)"
                            )
                    except Exception:
                        warnings.append(
                            f"Cleaning function '{func_name}' not found (will use defaults)"
                        )
        except ImportError:
            warnings.append("Could not import cleaning module to validate functions")

    sections["warnings"] = warnings

    return {
        "overall_valid": overall_valid,
        "sections": sections,
    }


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
    """Main validation CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate newspaper scraper configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s configs/fiji/fiji_sun.yaml          # Validate single file
  %(prog)s configs/fiji/fiji_sun.yaml -v       # Verbose output with details
  %(prog)s --all                               # Validate all configs
        """,
    )

    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        help="Path to the configuration file to validate",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output with detailed information",
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
        # Validate all configs using comprehensive validation
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
        print()

        passed = 0
        failed = 0

        for config_path in sorted(config_files):
            report = validate_config_comprehensive(config_path)

            # Brief summary for each file
            status_symbol = "✓" if report["overall_valid"] else "✗"
            print(
                f"{status_symbol} {config_path.stem}: {'PASS' if report['overall_valid'] else 'FAIL'}"
            )

            if report["overall_valid"]:
                passed += 1
            else:
                failed += 1

                # Show errors in non-verbose mode for failures
                if not args.verbose:
                    for section_name, section_data in report["sections"].items():
                        if isinstance(section_data, dict) and not section_data.get(
                            "valid", True
                        ):
                            for error in section_data.get("errors", []):
                                print(f"    - {error}")

        print()
        print("=" * 50)
        print(f"Summary: {passed} passed, {failed} failed")

        sys.exit(0 if failed == 0 else 1)

    elif args.config:
        # Validate single config with comprehensive validation
        if not args.config.exists():
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)

        print(f"Validating: {args.config}")
        print()

        report = validate_config_comprehensive(args.config)

        # Print report with checkmarks and X marks
        for section_name, section_data in report["sections"].items():
            if section_name == "warnings":
                for warning in section_data:
                    print(f"⚠  Warning: {warning}")
            elif section_name == "base_url":
                # Special handling for base_url (reachability check)
                if section_data.get("reachable"):
                    print(f"✓ {section_name}: OK (HTTP {section_data['status_code']})")
                else:
                    print(
                        f"⚠  {section_name}: {section_data.get('error', 'Unreachable')}"
                    )
                    if args.verbose and section_data.get("error"):
                        print(f"  - {section_data['error']}")
            elif isinstance(section_data, dict):
                if section_data.get("valid", True):
                    print(f"✓ {section_name}: OK")
                else:
                    print(f"✗ {section_name}: FAILED")
                    for error in section_data.get("errors", []):
                        print(f"  - {error}")

        print()
        if report["overall_valid"]:
            if report["sections"].get("warnings"):
                print("Validation passed with warnings")
                return 0
            else:
                print("Validation passed")
                return 0
        else:
            print("Validation failed")
            return 1

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
