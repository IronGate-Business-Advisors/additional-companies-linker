# src/config.py
"""
Configuration management and environment variable loading.

This module handles loading configuration from .env files and validating
that all required environment variables are present and valid.
"""

from dataclasses import dataclass
from typing import Optional, List
from dotenv import load_dotenv
import os

from .exceptions import ConfigurationError
from .models import (
    ProcessCompaniesMode,
    ProductNameFormat,
    ValueCalculationMode,
    QuantityMode,
    DuplicateAction,
    W2ChangeAction,
    ConfigIssue,
)


@dataclass
class Config:
    """
    Application configuration loaded from environment variables.

    Attributes:
        MongoDB connection settings
        Pipedrive API settings
        Product attachment behavior settings
        Migration settings
        Validation and safety settings
    """

    # MongoDB Settings
    mongodb_connection_string: str
    mongodb_database: str
    mongodb_collection: str

    # Pipedrive Settings
    pipedrive_api_key: str
    pipedrive_domain: str
    base_url: str

    # Product Attachment Behavior
    process_companies: ProcessCompaniesMode
    product_name_format: ProductNameFormat
    product_name_prefix: str
    product_code_generation: str
    value_calculation_mode: ValueCalculationMode
    item_price_per_employee: float
    fixed_product_price: float
    quantity_mode: QuantityMode
    custom_quantity: int

    # Duplicate Handling
    duplicate_attachment_action: DuplicateAction
    w2_change_action: W2ChangeAction
    duplicate_product_name_action: str

    # Product Catalog Management
    auto_create_products: bool
    product_visible_to: int
    product_active_flag: bool

    # Migration Settings
    migration_mode: bool
    migration_from: str
    migration_to: str
    migration_delete_old: bool
    migration_update_product_names: bool

    # Validation & Safety
    skip_orphaned_deals: bool
    skip_missing_w2: bool
    skip_zero_w2: bool
    min_w2_count: int
    max_w2_count: int
    require_confirmation: bool

    # Profile
    config_profile: Optional[str]

    @classmethod
    def load_from_env(cls, env_file: str = ".env") -> "Config":
        """
        Load configuration from .env file.

        Args:
            env_file: Path to .env file (default: ".env")

        Returns:
            Config instance with loaded values

        Raises:
            ConfigurationError: If required variables are missing or invalid
        """
        load_dotenv(env_file)

        # Load required MongoDB variables
        mongo_conn = os.getenv("MONGODB_CONNECTION_STRING")
        mongo_db = os.getenv("MONGODB_DATABASE")
        mongo_coll = os.getenv("MONGODB_COLLECTION")

        # Load required Pipedrive variables
        api_key = os.getenv("PIPEDRIVE_API_KEY")
        domain = os.getenv("PIPEDRIVE_DOMAIN")

        # Validate required variables
        missing = []
        if not mongo_conn:
            missing.append("MONGODB_CONNECTION_STRING")
        if not mongo_db:
            missing.append("MONGODB_DATABASE")
        if not mongo_coll:
            missing.append("MONGODB_COLLECTION")
        if not api_key:
            missing.append("PIPEDRIVE_API_KEY")
        if not domain:
            missing.append("PIPEDRIVE_DOMAIN")

        if missing:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Type narrowing
        assert mongo_conn is not None
        assert mongo_db is not None
        assert mongo_coll is not None
        assert api_key is not None
        assert domain is not None

        # Clean up domain
        domain = domain.replace("https://", "").replace("http://", "").strip()
        base_url = f"https://{domain}/api/v1"

        # Check for profile first
        profile = os.getenv("CONFIG_PROFILE")
        if profile:
            # Load profile defaults
            config = cls._load_profile_defaults(profile)
        else:
            # Load individual settings with defaults
            config = cls._load_default_config()

        # Override with explicit environment variables
        config.mongodb_connection_string = mongo_conn
        config.mongodb_database = mongo_db
        config.mongodb_collection = mongo_coll
        config.pipedrive_api_key = api_key
        config.pipedrive_domain = domain
        config.base_url = base_url

        # Load optional overrides
        config._apply_env_overrides()

        return config

    @classmethod
    def _load_profile_defaults(cls, profile: str) -> "Config":
        """Load configuration from predefined profile."""
        profiles = {
            "standard": cls._get_standard_profile(),
            "conservative": cls._get_conservative_profile(),
            "aggressive": cls._get_aggressive_profile(),
            "migration": cls._get_migration_profile(),
        }

        if profile not in profiles:
            raise ConfigurationError(
                f"Invalid profile: {profile}. Valid profiles: {', '.join(profiles.keys())}"
            )

        return profiles[profile]

    @classmethod
    def _get_standard_profile(cls) -> "Config":
        """Standard profile with sensible defaults."""
        return Config(
            # Required fields (will be overridden)
            mongodb_connection_string="",
            mongodb_database="",
            mongodb_collection="",
            pipedrive_api_key="",
            pipedrive_domain="",
            base_url="",
            # Profile defaults
            process_companies=ProcessCompaniesMode.ADDITIONAL_ONLY,
            product_name_format=ProductNameFormat.COMPANY_NAME,
            product_name_prefix="",
            product_code_generation="none",
            value_calculation_mode=ValueCalculationMode.W2_COUNT_TIMES_PRICE,
            item_price_per_employee=1.0,
            fixed_product_price=100.0,
            quantity_mode=QuantityMode.W2_COUNT,
            custom_quantity=1,
            duplicate_attachment_action=DuplicateAction.UPDATE,
            w2_change_action=W2ChangeAction.UPDATE_BOTH,
            duplicate_product_name_action="create_with_suffix",
            auto_create_products=True,
            product_visible_to=3,
            product_active_flag=True,
            migration_mode=False,
            migration_from="",
            migration_to="",
            migration_delete_old=False,
            migration_update_product_names=False,
            skip_orphaned_deals=True,
            skip_missing_w2=True,
            skip_zero_w2=True,
            min_w2_count=0,
            max_w2_count=10000,
            require_confirmation=True,
            config_profile="standard",
        )

    @classmethod
    def _get_conservative_profile(cls) -> "Config":
        """Conservative profile - safer, requires manual review."""
        config = cls._get_standard_profile()
        config.duplicate_attachment_action = DuplicateAction.SKIP
        config.duplicate_product_name_action = "error"
        config.auto_create_products = False
        config.require_confirmation = True
        config.config_profile = "conservative"
        return config

    @classmethod
    def _get_aggressive_profile(cls) -> "Config":
        """Aggressive profile - auto-fix everything."""
        config = cls._get_standard_profile()
        config.process_companies = ProcessCompaniesMode.BOTH
        config.duplicate_attachment_action = DuplicateAction.UPDATE
        config.w2_change_action = W2ChangeAction.UPDATE_BOTH
        config.require_confirmation = False
        config.config_profile = "aggressive"
        return config

    @classmethod
    def _get_migration_profile(cls) -> "Config":
        """Migration profile - for changing specifications."""
        config = cls._get_standard_profile()
        config.migration_mode = True
        config.duplicate_attachment_action = DuplicateAction.UPDATE
        config.migration_update_product_names = True
        config.config_profile = "migration"
        return config

    @classmethod
    def _load_default_config(cls) -> "Config":
        """Load default configuration without profile."""
        return cls._get_standard_profile()

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        # Product Attachment Behavior
        if os.getenv("PROCESS_COMPANIES"):
            self.process_companies = ProcessCompaniesMode(
                os.getenv("PROCESS_COMPANIES")
            )

        if os.getenv("PRODUCT_NAME_FORMAT"):
            self.product_name_format = ProductNameFormat(
                os.getenv("PRODUCT_NAME_FORMAT")
            )

        if os.getenv("PRODUCT_NAME_PREFIX"):
            self.product_name_prefix = os.getenv("PRODUCT_NAME_PREFIX", "")

        if os.getenv("VALUE_CALCULATION_MODE"):
            self.value_calculation_mode = ValueCalculationMode(
                os.getenv("VALUE_CALCULATION_MODE")
            )

        if os.getenv("ITEM_PRICE_PER_EMPLOYEE"):
            self.item_price_per_employee = float(
                os.getenv("ITEM_PRICE_PER_EMPLOYEE", "1.0")
            )

        if os.getenv("QUANTITY_MODE"):
            self.quantity_mode = QuantityMode(os.getenv("QUANTITY_MODE"))

        if os.getenv("DUPLICATE_ATTACHMENT_ACTION"):
            self.duplicate_attachment_action = DuplicateAction(
                os.getenv("DUPLICATE_ATTACHMENT_ACTION")
            )

        # Boolean overrides
        if os.getenv("AUTO_CREATE_PRODUCTS"):
            self.auto_create_products = os.getenv("AUTO_CREATE_PRODUCTS", "").lower() == "true"

        if os.getenv("SKIP_ORPHANED_DEALS"):
            self.skip_orphaned_deals = os.getenv("SKIP_ORPHANED_DEALS", "").lower() == "true"

        if os.getenv("MIGRATION_MODE"):
            self.migration_mode = os.getenv("MIGRATION_MODE", "").lower() == "true"

        # Integer overrides
        if os.getenv("MIN_W2_COUNT"):
            self.min_w2_count = int(os.getenv("MIN_W2_COUNT", "0"))

        if os.getenv("MAX_W2_COUNT"):
            self.max_w2_count = int(os.getenv("MAX_W2_COUNT", "10000"))

    def validate(self) -> List[ConfigIssue]:
        """
        Validate configuration for conflicts and issues.

        Returns:
            List of configuration issues (errors and warnings)
        """
        issues: List[ConfigIssue] = []

        # Check for conflicting settings
        if self.migration_mode and not self.migration_from:
            issues.append(
                ConfigIssue(
                    level="ERROR",
                    message="MIGRATION_MODE=true requires MIGRATION_FROM to be set",
                )
            )

        if (
            self.quantity_mode == QuantityMode.W2_COUNT
            and self.value_calculation_mode == ValueCalculationMode.FIXED_PRICE
        ):
            issues.append(
                ConfigIssue(
                    level="WARNING",
                    message="Using W2 quantity with fixed price may produce unexpected values",
                )
            )

        if self.duplicate_attachment_action == DuplicateAction.FORCE_NEW:
            issues.append(
                ConfigIssue(
                    level="WARNING",
                    message="FORCE_NEW will create duplicate attachments - use with caution",
                )
            )

        if not self.auto_create_products and self.process_companies == ProcessCompaniesMode.BOTH:
            issues.append(
                ConfigIssue(
                    level="WARNING",
                    message="Processing both company types but not auto-creating products",
                )
            )

        if self.max_w2_count > 0 and self.max_w2_count < self.min_w2_count:
            issues.append(
                ConfigIssue(
                    level="ERROR", message="MAX_W2_COUNT must be greater than MIN_W2_COUNT"
                )
            )

        if self.item_price_per_employee <= 0:
            issues.append(
                ConfigIssue(
                    level="ERROR",
                    message="ITEM_PRICE_PER_EMPLOYEE must be greater than 0",
                )
            )

        if self.migration_mode and self.migration_delete_old:
            issues.append(
                ConfigIssue(
                    level="WARNING",
                    message="Migration with delete enabled - this will remove old attachments",
                )
            )

        return issues

    def get_summary(self) -> str:
        """
        Get a human-readable configuration summary.

        Returns:
            Formatted configuration summary string
        """
        lines = [
            "Configuration Summary",
            "=" * 60,
            f"Profile: {self.config_profile or 'custom'}",
            "",
            "Companies to Process:",
            f"  {self.process_companies.value}",
            "",
            "Product Settings:",
            f"  Name Format: {self.product_name_format.value}",
            f"  Name Prefix: {self.product_name_prefix or '(none)'}",
            f"  Auto-create: {self.auto_create_products}",
            "",
            "Value Calculation:",
            f"  Mode: {self.value_calculation_mode.value}",
            f"  Price per Employee: ${self.item_price_per_employee}",
            f"  Quantity Mode: {self.quantity_mode.value}",
            "",
            "Duplicate Handling:",
            f"  Attachment Action: {self.duplicate_attachment_action.value}",
            f"  W2 Change Action: {self.w2_change_action.value}",
            "",
            "Safety Settings:",
            f"  Skip Orphaned Deals: {self.skip_orphaned_deals}",
            f"  Skip Missing W2: {self.skip_missing_w2}",
            f"  Min W2 Count: {self.min_w2_count}",
            f"  Max W2 Count: {self.max_w2_count}",
            "",
            "Migration:",
            f"  Enabled: {self.migration_mode}",
        ]

        if self.migration_mode:
            lines.extend(
                [
                    f"  From: {self.migration_from}",
                    f"  To: {self.migration_to}",
                    f"  Delete Old: {self.migration_delete_old}",
                ]
            )

        return "\n".join(lines)
