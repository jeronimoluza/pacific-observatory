"""
Metadata JSON handling for scraping runs.

Manages metadata.json files that store scraping statistics and results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MetadataHandler:
    """Handles metadata JSON file operations."""

    def __init__(self, base_data_dir: Path):
        """
        Initialize metadata handler.

        Args:
            base_data_dir: Base directory for data storage
        """
        self.base_data_dir = base_data_dir

    def serialize_for_json(self, obj: Any) -> Any:
        """
        Recursively serialize objects to ensure JSON compatibility.

        Converts HttpUrl objects and other non-serializable types to strings.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable version of the object
        """
        # More robust HttpUrl detection
        if hasattr(obj, "__class__"):
            class_name = obj.__class__.__name__
            module_name = getattr(obj.__class__, "__module__", "")
            if (
                "HttpUrl" in class_name
                or "pydantic" in module_name
                and "Url" in class_name
            ):
                return str(obj)

        # Handle Pydantic models by converting to dict first
        if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            try:
                # This is likely a Pydantic model
                model_dict = obj.dict()
                return self.serialize_for_json(model_dict)
            except Exception:
                # If dict() fails, convert to string
                return str(obj)

        # Handle collections recursively
        if isinstance(obj, dict):
            return {key: self.serialize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self.serialize_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self.serialize_for_json(item) for item in obj)
        else:
            # For any other object that might not be JSON serializable, try to convert to string
            try:
                json.dumps(obj)
                return obj  # It's already JSON serializable
            except (TypeError, ValueError):
                return str(obj)  # Convert non-serializable objects to string

    def save_metadata(
        self,
        results: Dict[str, Any],
        newspaper_dir: Path,
        country: str,
        newspaper: str,
        timestamp: datetime = None,
        metadata_type: str = "news",
    ) -> Path:
        """
        Save scraping metadata and statistics.

        Args:
            results: Scraping results dictionary
            newspaper_dir: Directory for the newspaper
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for filename
            metadata_type: Type of metadata ("urls" or "news")

        Returns:
            Path to the saved metadata file
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Create metadata directory
        metadata_dir = newspaper_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)

        # Create filename based on metadata type
        filename = (
            f"{metadata_type}_metadata_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        )
        file_path = metadata_dir / filename

        # Prepare metadata
        metadata = {
            "newspaper": newspaper,
            "country": country,
            "scraped_at": timestamp.isoformat(),
            "success": results.get("success", False),
            "statistics": results.get("statistics", {}),
            "errors": results.get("errors", []),
            "config_info": {
                "config_path": results.get("_config_path"),
                "client_type": results.get("client_type"),
            },
        }

        # Serialize metadata to handle HttpUrl objects
        serialized_metadata = self.serialize_for_json(metadata)

        # Save metadata
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(serialized_metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved metadata to {file_path}")
        return file_path
