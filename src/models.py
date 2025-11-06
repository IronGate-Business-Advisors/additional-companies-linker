# src/models.py
"""
Data models for submissions, products, attachments, and results.

This module defines all the core data structures used throughout
the product linking and migration process.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================


class ProcessCompaniesMode(str, Enum):
    """Which companies to process as products."""

    ADDITIONAL_ONLY = "additional_only"
    PRIMARY_ONLY = "primary_only"
    BOTH = "both"


class ProductNameFormat(str, Enum):
    """How to format product names."""

    COMPANY_NAME = "company_name"
    COMPANY_NAME_WITH_PREFIX = "company_name_with_prefix"
    CUSTOM_FORMAT = "custom_format"


class ValueCalculationMode(str, Enum):
    """How to calculate product value."""

    W2_COUNT = "w2_count"  # Value = W2 count (quantity=1, price=W2)
    W2_COUNT_TIMES_PRICE = "w2_count_times_price"  # Value = W2 × price (quantity=W2, price=fixed)
    FIXED_PRICE = "fixed_price"  # Value = fixed (quantity=1, price=fixed)


class QuantityMode(str, Enum):
    """How to set product quantity."""

    W2_COUNT = "w2_count"
    ALWAYS_ONE = "always_one"
    CUSTOM = "custom"


class DuplicateAction(str, Enum):
    """What to do if product already attached to deal."""

    UPDATE = "update"  # Update quantity/price
    SKIP = "skip"  # Skip if already attached
    ERROR = "error"  # Raise error
    FORCE_NEW = "force_new"  # Create duplicate (dangerous)


class W2ChangeAction(str, Enum):
    """What to do if W2 count changed."""

    UPDATE_QUANTITY = "update_quantity"
    UPDATE_PRICE = "update_price"
    UPDATE_BOTH = "update_both"
    SKIP = "skip"


class LinkStatus(str, Enum):
    """Possible outcomes of a product linking attempt."""

    SUCCESS = "success"
    UPDATED = "updated"
    SKIPPED = "skipped"
    NO_DEAL_ID = "no_deal_id"
    NO_COMPANIES = "no_companies"
    ORPHANED = "orphaned"
    FAILED_ERROR = "failed_error"


class ProductActionType(str, Enum):
    """Type of action performed on a product."""

    CREATED_CATALOG = "created_catalog"  # Created new product in catalog
    FOUND_CATALOG = "found_catalog"  # Found existing product in catalog
    ATTACHED_NEW = "attached_new"  # Attached product to deal (new)
    UPDATED_QUANTITY = "updated_quantity"  # Updated existing attachment quantity
    UPDATED_PRICE = "updated_price"  # Updated existing attachment price
    SKIPPED_EXISTS = "skipped_exists"  # Skipped, already correct
    ERROR = "error"  # Failed with error


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class AdditionalCompany:
    """
    Represents an additional company from MongoDB submission.

    Attributes:
        company_legal_name: Legal name of the company
        w2_employee_count: Number of W2 employees
        raw_data: Full nested object for reference
    """

    company_legal_name: str
    w2_employee_count: Optional[int]
    raw_data: Dict[str, Any]


@dataclass
class Submission:
    """
    Represents a MongoDB submission document.

    Attributes:
        id: MongoDB _id as string
        deal_id: Linked Pipedrive deal ID
        primary_company: Primary company information
        additional_companies: List of additional companies
        email: Client email from data.email
        raw_data: Full document data for reference
    """

    id: str
    deal_id: Optional[int]
    primary_company: Optional[AdditionalCompany]
    additional_companies: List[AdditionalCompany]
    email: str
    raw_data: Dict[str, Any]


@dataclass
class PipedriveProduct:
    """
    Represents a product in Pipedrive catalog.

    Attributes:
        id: Unique product identifier
        name: Product name
        code: Product code (optional)
        active_flag: Whether product is active
        prices: List of product prices
    """

    id: int
    name: str
    code: Optional[str]
    active_flag: bool
    prices: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DealProductAttachment:
    """
    Represents a product attachment to a deal.

    Attributes:
        id: Attachment ID (unique per deal-product link)
        product_id: Reference to product in catalog
        deal_id: Deal ID
        item_price: Price per unit
        quantity: Number of units
        sum: Total value (quantity × price)
        name: Product name (denormalized)
        comments: Optional comments on attachment
    """

    id: int
    product_id: int
    deal_id: int
    item_price: float
    quantity: int
    sum: float
    name: str
    comments: Optional[str] = None


@dataclass
class ProductAction:
    """
    Represents a single action taken on a product/attachment.

    Attributes:
        company_name: Name of company processed
        w2_count: W2 employee count
        action_type: Type of action performed
        product_id: Product ID (if applicable)
        attachment_id: Attachment ID (if applicable)
        old_quantity: Previous quantity (for updates)
        new_quantity: New quantity (for updates)
        old_price: Previous price (for updates)
        new_price: New price (for updates)
        error_message: Error details if failed
    """

    company_name: str
    w2_count: Optional[int]
    action_type: ProductActionType
    product_id: Optional[int] = None
    attachment_id: Optional[int] = None
    old_quantity: Optional[int] = None
    new_quantity: Optional[int] = None
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class LinkResult:
    """
    Result of processing a single submission.

    Attributes:
        submission_id: MongoDB submission _id
        deal_id: Pipedrive deal ID
        status: Overall outcome status
        companies_processed: Number of companies processed
        actions: List of actions performed
        total_value_added: Total monetary value added to deal
        error_message: Error details if failed
    """

    submission_id: str
    deal_id: Optional[int]
    status: LinkStatus
    companies_processed: int
    actions: List[ProductAction]
    total_value_added: float
    error_message: Optional[str] = None

    @property
    def products_created(self) -> int:
        """Count of products created in catalog."""
        return sum(
            1
            for a in self.actions
            if a.action_type == ProductActionType.CREATED_CATALOG
        )

    @property
    def products_found(self) -> int:
        """Count of products found in catalog."""
        return sum(
            1 for a in self.actions if a.action_type == ProductActionType.FOUND_CATALOG
        )

    @property
    def attachments_created(self) -> int:
        """Count of new attachments created."""
        return sum(
            1 for a in self.actions if a.action_type == ProductActionType.ATTACHED_NEW
        )

    @property
    def attachments_updated(self) -> int:
        """Count of attachments updated."""
        return sum(
            1
            for a in self.actions
            if a.action_type
            in (ProductActionType.UPDATED_QUANTITY, ProductActionType.UPDATED_PRICE)
        )

    @property
    def attachments_skipped(self) -> int:
        """Count of attachments skipped."""
        return sum(
            1
            for a in self.actions
            if a.action_type == ProductActionType.SKIPPED_EXISTS
        )

    @property
    def errors(self) -> int:
        """Count of errors."""
        return sum(1 for a in self.actions if a.action_type == ProductActionType.ERROR)


@dataclass
class Deal:
    """
    Represents a Pipedrive deal.

    Attributes:
        id: Unique deal identifier
        title: Deal title/name
        value: Deal monetary value
        stage_id: Current stage ID
        pipeline_id: Current pipeline ID
        org_id: Organization ID (if linked)
    """

    id: int
    title: str
    value: Optional[float]
    stage_id: int
    pipeline_id: int
    org_id: Optional[int]


@dataclass
class BackupEntry:
    """
    Represents a backup entry for a submission.

    Attributes:
        submission_id: MongoDB submission _id
        deal_id: Pipedrive deal ID
        deal_value_before: Deal value before changes
        products_before: List of product attachments before changes
        timestamp: When backup was created
    """

    submission_id: str
    deal_id: int
    deal_value_before: float
    products_before: List[Dict[str, Any]]
    timestamp: str


@dataclass
class ConfigIssue:
    """
    Represents a configuration validation issue.

    Attributes:
        level: Issue severity (ERROR, WARNING, INFO)
        message: Description of the issue
    """

    level: str  # "ERROR", "WARNING", "INFO"
    message: str
