# src/exceptions.py
"""
Custom exceptions for the Additional Companies Product Linker.

This module defines the exception hierarchy used throughout the application
for clear error handling and reporting.
"""

from typing import Optional


class LinkerError(Exception):
    """Base exception for all linker-related errors."""

    pass


class ConfigurationError(LinkerError):
    """
    Raised when configuration is invalid or incomplete.

    Examples:
        - Missing environment variables
        - Invalid .env file
        - Conflicting configuration options
    """

    pass


class MongoDBError(LinkerError):
    """
    Raised when MongoDB operations fail.

    Examples:
        - Connection failures
        - Query errors
        - Document parsing errors
    """

    pass


class APIError(LinkerError):
    """
    Raised when Pipedrive API calls fail.

    Attributes:
        status_code: HTTP status code (if available)
    """

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(APIError):
    """
    Raised when API rate limiting occurs (429 errors).

    This exception triggers exponential backoff retry logic.
    """

    pass


class ValidationError(LinkerError):
    """
    Raised when data validation fails.

    Examples:
        - Missing required fields
        - Invalid W2 counts
        - Malformed data structures
    """

    pass


class ProductNotFoundError(LinkerError):
    """
    Raised when a required product doesn't exist in Pipedrive catalog.

    Attributes:
        product_name: Name of the product that wasn't found
    """

    def __init__(self, message: str, product_name: str):
        super().__init__(message)
        self.product_name = product_name


class OrphanedDealError(LinkerError):
    """
    Raised when a dealId exists in MongoDB but the deal doesn't exist in Pipedrive.

    Attributes:
        deal_id: The orphaned deal ID
        submission_id: MongoDB submission ID
    """

    def __init__(self, message: str, deal_id: int, submission_id: str):
        super().__init__(message)
        self.deal_id = deal_id
        self.submission_id = submission_id


class DuplicateAttachmentError(LinkerError):
    """
    Raised when attempting to create duplicate product attachment.

    Attributes:
        product_id: The product ID
        deal_id: The deal ID
        attachment_id: Existing attachment ID
    """

    def __init__(
        self, message: str, product_id: int, deal_id: int, attachment_id: int
    ):
        super().__init__(message)
        self.product_id = product_id
        self.deal_id = deal_id
        self.attachment_id = attachment_id


class MigrationError(LinkerError):
    """
    Raised when migration operations fail.

    Examples:
        - Invalid migration configuration
        - Backup file corruption
        - Rollback failures
    """

    pass
