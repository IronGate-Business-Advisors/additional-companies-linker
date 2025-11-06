# src/product_linker.py
"""
Product linking orchestration.

This module handles the process of linking additional companies from MongoDB
to Pipedrive deals as product attachments.
"""

import logging
from typing import List, Tuple, Optional

from .config import Config
from .models import (
    Submission,
    AdditionalCompany,
    PipedriveProduct,
    DealProductAttachment,
    LinkResult,
    ProductAction,
    LinkStatus,
    ProductActionType,
    ProcessCompaniesMode,
    ValueCalculationMode,
    QuantityMode,
    DuplicateAction,
    W2ChangeAction,
    ProductNameFormat,
)
from .pipedrive_client import PipedriveClient
from .exceptions import (
    OrphanedDealError,
    APIError,
)

logger = logging.getLogger(__name__)


class ProductLinker:
    """
    Orchestrates the product linking process.

    Attributes:
        config: Application configuration
        pipedrive_client: Pipedrive API client
    """

    def __init__(self, config: Config, pipedrive_client: PipedriveClient):
        """
        Initialize product linker.

        Args:
            config: Application configuration
            pipedrive_client: Pipedrive API client instance
        """
        self.config = config
        self.pipedrive_client = pipedrive_client

    def link_submission(
        self, submission: Submission, dry_run: bool = False
    ) -> LinkResult:
        """
        Process a single submission and attach company products to deal.

        Args:
            submission: Submission to process
            dry_run: If True, preview only without making changes

        Returns:
            LinkResult with outcome
        """
        # Validate submission has dealId
        if submission.deal_id is None:
            return LinkResult(
                submission_id=submission.id,
                deal_id=None,
                status=LinkStatus.NO_DEAL_ID,
                companies_processed=0,
                actions=[],
                total_value_added=0.0,
                error_message="No dealId in submission",
            )

        # Get companies to process based on configuration
        companies = self._get_companies_to_process(submission)

        if not companies:
            return LinkResult(
                submission_id=submission.id,
                deal_id=submission.deal_id,
                status=LinkStatus.NO_COMPANIES,
                companies_processed=0,
                actions=[],
                total_value_added=0.0,
                error_message="No companies to process",
            )

        # Verify deal exists
        try:
            deal = self.pipedrive_client.get_deal_by_id(submission.deal_id)
            if deal is None:
                if self.config.skip_orphaned_deals:
                    return LinkResult(
                        submission_id=submission.id,
                        deal_id=submission.deal_id,
                        status=LinkStatus.ORPHANED,
                        companies_processed=0,
                        actions=[],
                        total_value_added=0.0,
                        error_message=f"Deal {submission.deal_id} not found in Pipedrive",
                    )
                else:
                    raise OrphanedDealError(
                        f"Deal {submission.deal_id} not found",
                        submission.deal_id,
                        submission.id,
                    )
        except APIError as e:
            return LinkResult(
                submission_id=submission.id,
                deal_id=submission.deal_id,
                status=LinkStatus.FAILED_ERROR,
                companies_processed=0,
                actions=[],
                total_value_added=0.0,
                error_message=f"Failed to verify deal: {str(e)}",
            )

        # Fetch current products on deal (for duplicate checking)
        try:
            current_attachments = self.pipedrive_client.get_deal_products(
                submission.deal_id
            )
        except APIError as e:
            return LinkResult(
                submission_id=submission.id,
                deal_id=submission.deal_id,
                status=LinkStatus.FAILED_ERROR,
                companies_processed=0,
                actions=[],
                total_value_added=0.0,
                error_message=f"Failed to fetch deal products: {str(e)}",
            )

        # Process each company
        actions: List[ProductAction] = []
        total_value = 0.0

        for company in companies:
            action = self._process_company(
                company, submission.deal_id, current_attachments, dry_run
            )
            actions.append(action)

            # Calculate value added
            if action.action_type in (
                ProductActionType.ATTACHED_NEW,
                ProductActionType.UPDATED_QUANTITY,
                ProductActionType.UPDATED_PRICE,
            ):
                if action.new_quantity is not None and action.new_price is not None:
                    total_value += action.new_quantity * action.new_price

        # Determine overall status
        has_success = any(
            a.action_type
            in (
                ProductActionType.ATTACHED_NEW,
                ProductActionType.UPDATED_QUANTITY,
                ProductActionType.UPDATED_PRICE,
            )
            for a in actions
        )
        has_errors = any(a.action_type == ProductActionType.ERROR for a in actions)

        if has_errors and not has_success:
            status = LinkStatus.FAILED_ERROR
        elif has_success:
            status = LinkStatus.SUCCESS
        elif any(a.action_type == ProductActionType.SKIPPED_EXISTS for a in actions):
            status = LinkStatus.SKIPPED
        else:
            status = LinkStatus.FAILED_ERROR

        return LinkResult(
            submission_id=submission.id,
            deal_id=submission.deal_id,
            status=status,
            companies_processed=len(companies),
            actions=actions,
            total_value_added=total_value,
            error_message=None,
        )

    def _get_companies_to_process(
        self, submission: Submission
    ) -> List[AdditionalCompany]:
        """
        Get list of companies to process based on configuration.

        Args:
            submission: Submission to extract companies from

        Returns:
            List of companies to process
        """
        companies: List[AdditionalCompany] = []

        process_mode = self.config.process_companies

        # Add primary company if configured
        if process_mode in (ProcessCompaniesMode.PRIMARY_ONLY, ProcessCompaniesMode.BOTH):
            if submission.primary_company:
                companies.append(submission.primary_company)

        # Add additional companies if configured
        if process_mode in (
            ProcessCompaniesMode.ADDITIONAL_ONLY,
            ProcessCompaniesMode.BOTH,
        ):
            companies.extend(submission.additional_companies)

        return companies

    def _process_company(
        self,
        company: AdditionalCompany,
        deal_id: int,
        current_attachments: List[DealProductAttachment],
        dry_run: bool,
    ) -> ProductAction:
        """
        Process a single company (create/attach product).

        Args:
            company: Company to process
            deal_id: Deal ID to attach to
            current_attachments: Current products on deal
            dry_run: If True, preview only

        Returns:
            ProductAction with outcome
        """
        try:
            # Validate company data
            validation_error = self._validate_company(company)
            if validation_error:
                return ProductAction(
                    company_name=company.company_legal_name,
                    w2_count=company.w2_employee_count,
                    action_type=ProductActionType.ERROR,
                    error_message=validation_error,
                )

            # Format product name
            product_name = self._format_product_name(company.company_legal_name)

            # Find or create product in catalog
            product, catalog_action = self._find_or_create_product(
                product_name, dry_run
            )

            if product is None:
                return ProductAction(
                    company_name=company.company_legal_name,
                    w2_count=company.w2_employee_count,
                    action_type=ProductActionType.ERROR,
                    error_message="Failed to find or create product",
                )

            # Calculate quantity and price
            quantity, price = self._calculate_quantity_and_price(
                company.w2_employee_count
            )

            # Check if product already attached
            existing_attachment = self._find_existing_attachment(
                product.id, current_attachments
            )

            if existing_attachment:
                # Handle duplicate attachment
                action = self._handle_duplicate_attachment(
                    company,
                    product,
                    existing_attachment,
                    quantity,
                    price,
                    deal_id,
                    dry_run,
                )
            else:
                # Attach new product
                action = self._attach_new_product(
                    company, product, quantity, price, deal_id, dry_run
                )

            # Set catalog action type if it was a creation
            if catalog_action and action.action_type != ProductActionType.ERROR:
                action.action_type = catalog_action

            return action

        except Exception as e:
            logger.error(f"Error processing company {company.company_legal_name}: {str(e)}")
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.ERROR,
                error_message=str(e),
            )

    def _validate_company(self, company: AdditionalCompany) -> Optional[str]:
        """
        Validate company data.

        Args:
            company: Company to validate

        Returns:
            Error message if invalid, None if valid
        """
        # Check if W2 count is missing
        if company.w2_employee_count is None:
            if self.config.skip_missing_w2:
                return "Missing W2 employee count"
            else:
                return None  # Will use default

        # Check if W2 count is zero
        if company.w2_employee_count == 0:
            if self.config.skip_zero_w2:
                return "W2 employee count is zero"

        # Check if W2 count is below minimum
        if (
            self.config.min_w2_count > 0
            and company.w2_employee_count < self.config.min_w2_count
        ):
            return f"W2 count ({company.w2_employee_count}) below minimum ({self.config.min_w2_count})"

        # Check if W2 count exceeds maximum
        if (
            self.config.max_w2_count > 0
            and company.w2_employee_count > self.config.max_w2_count
        ):
            return f"W2 count ({company.w2_employee_count}) exceeds maximum ({self.config.max_w2_count})"

        return None

    def _format_product_name(self, company_name: str) -> str:
        """
        Format product name based on configuration.

        Args:
            company_name: Raw company name

        Returns:
            Formatted product name
        """
        # Normalize name
        name = company_name.strip().rstrip(".")

        format_mode = self.config.product_name_format

        if format_mode == ProductNameFormat.COMPANY_NAME:
            return name

        elif format_mode == ProductNameFormat.COMPANY_NAME_WITH_PREFIX:
            prefix = self.config.product_name_prefix
            return f"{prefix}{name}"

        elif format_mode == ProductNameFormat.CUSTOM_FORMAT:
            # Could be extended with custom formatting logic
            return name

        return name

    def _find_or_create_product(
        self, product_name: str, dry_run: bool
    ) -> Tuple[Optional[PipedriveProduct], Optional[ProductActionType]]:
        """
        Find product in catalog or create if doesn't exist.

        Args:
            product_name: Name of product to find/create
            dry_run: If True, don't actually create

        Returns:
            Tuple of (Product, ActionType) or (None, None) if failed
        """
        # Search for existing product
        product = self.pipedrive_client.search_product_by_name(
            product_name, exact_match=True
        )

        if product:
            return product, ProductActionType.FOUND_CATALOG

        # Product doesn't exist - create if configured
        if self.config.auto_create_products:
            if dry_run:
                # In dry run, simulate product creation
                from .models import PipedriveProduct

                dummy_product = PipedriveProduct(
                    id=999999,  # Dummy ID for dry run
                    name=product_name,
                    code=None,
                    active_flag=True,
                    prices=[],
                )
                return dummy_product, ProductActionType.CREATED_CATALOG

            # Actually create product
            try:
                product = self.pipedrive_client.create_product(
                    name=product_name,
                    code=None,
                    active=self.config.product_active_flag,
                    visible_to=self.config.product_visible_to,
                )
                return product, ProductActionType.CREATED_CATALOG
            except APIError as e:
                logger.error(f"Failed to create product {product_name}: {str(e)}")
                return None, None

        # Product doesn't exist and not auto-creating
        return None, None

    def _calculate_quantity_and_price(
        self, w2_count: Optional[int]
    ) -> Tuple[int, float]:
        """
        Calculate quantity and price based on configuration.

        Args:
            w2_count: W2 employee count (may be None)

        Returns:
            Tuple of (quantity, price)
        """
        # Default W2 count if missing
        effective_w2 = w2_count if w2_count is not None else 1

        calc_mode = self.config.value_calculation_mode
        quantity_mode = self.config.quantity_mode

        # Determine quantity
        if quantity_mode == QuantityMode.W2_COUNT:
            quantity = effective_w2
        elif quantity_mode == QuantityMode.ALWAYS_ONE:
            quantity = 1
        elif quantity_mode == QuantityMode.CUSTOM:
            quantity = self.config.custom_quantity
        else:
            quantity = effective_w2

        # Determine price
        if calc_mode == ValueCalculationMode.W2_COUNT:
            # Quantity=1, Price=W2 count
            price = float(effective_w2)
        elif calc_mode == ValueCalculationMode.W2_COUNT_TIMES_PRICE:
            # Quantity=W2 count, Price=fixed per employee
            price = self.config.item_price_per_employee
        elif calc_mode == ValueCalculationMode.FIXED_PRICE:
            # Quantity=1, Price=fixed
            price = self.config.fixed_product_price
        else:
            price = self.config.item_price_per_employee

        return quantity, price

    def _find_existing_attachment(
        self, product_id: int, attachments: List[DealProductAttachment]
    ) -> Optional[DealProductAttachment]:
        """
        Find if product is already attached to deal.

        Args:
            product_id: Product ID to search for
            attachments: List of current attachments

        Returns:
            DealProductAttachment if found, None otherwise
        """
        for attachment in attachments:
            if attachment.product_id == product_id:
                return attachment
        return None

    def _handle_duplicate_attachment(
        self,
        company: AdditionalCompany,
        product: PipedriveProduct,
        existing_attachment: DealProductAttachment,
        new_quantity: int,
        new_price: float,
        deal_id: int,
        dry_run: bool,
    ) -> ProductAction:
        """
        Handle case where product is already attached to deal.

        Args:
            company: Company being processed
            product: Product being attached
            existing_attachment: Existing attachment on deal
            new_quantity: Calculated new quantity
            new_price: Calculated new price
            deal_id: Deal ID
            dry_run: If True, preview only

        Returns:
            ProductAction with outcome
        """
        action_type_config = self.config.duplicate_attachment_action

        # Check if values match
        quantity_matches = existing_attachment.quantity == new_quantity
        price_matches = abs(existing_attachment.item_price - new_price) < 0.01

        if quantity_matches and price_matches:
            # Already attached with correct values
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.SKIPPED_EXISTS,
                product_id=product.id,
                attachment_id=existing_attachment.id,
                old_quantity=existing_attachment.quantity,
                new_quantity=new_quantity,
                old_price=existing_attachment.item_price,
                new_price=new_price,
            )

        # Values don't match - check what to do
        if action_type_config == DuplicateAction.SKIP:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.SKIPPED_EXISTS,
                product_id=product.id,
                attachment_id=existing_attachment.id,
                old_quantity=existing_attachment.quantity,
                new_quantity=new_quantity,
                old_price=existing_attachment.item_price,
                new_price=new_price,
            )

        elif action_type_config == DuplicateAction.UPDATE:
            # Update attachment
            return self._update_attachment(
                company,
                product,
                existing_attachment,
                new_quantity,
                new_price,
                deal_id,
                dry_run,
            )

        elif action_type_config == DuplicateAction.ERROR:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.ERROR,
                product_id=product.id,
                error_message="Product already attached (configured to error)",
            )

        else:  # FORCE_NEW - create duplicate (dangerous)
            return self._attach_new_product(
                company, product, new_quantity, new_price, deal_id, dry_run
            )

    def _update_attachment(
        self,
        company: AdditionalCompany,
        product: PipedriveProduct,
        existing_attachment: DealProductAttachment,
        new_quantity: int,
        new_price: float,
        deal_id: int,
        dry_run: bool,
    ) -> ProductAction:
        """
        Update existing product attachment.

        Args:
            company: Company being processed
            product: Product being updated
            existing_attachment: Existing attachment
            new_quantity: New quantity
            new_price: New price
            deal_id: Deal ID
            dry_run: If True, preview only

        Returns:
            ProductAction with outcome
        """
        # Determine what changed
        quantity_changed = existing_attachment.quantity != new_quantity
        price_changed = abs(existing_attachment.item_price - new_price) > 0.01

        w2_action_config = self.config.w2_change_action

        # Determine what to update
        update_quantity = False
        update_price = False

        if w2_action_config == W2ChangeAction.UPDATE_QUANTITY:
            update_quantity = quantity_changed
        elif w2_action_config == W2ChangeAction.UPDATE_PRICE:
            update_price = price_changed
        elif w2_action_config == W2ChangeAction.UPDATE_BOTH:
            update_quantity = quantity_changed
            update_price = price_changed
        elif w2_action_config == W2ChangeAction.SKIP:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.SKIPPED_EXISTS,
                product_id=product.id,
                attachment_id=existing_attachment.id,
                old_quantity=existing_attachment.quantity,
                new_quantity=new_quantity,
                old_price=existing_attachment.item_price,
                new_price=new_price,
            )

        if not update_quantity and not update_price:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.SKIPPED_EXISTS,
                product_id=product.id,
                attachment_id=existing_attachment.id,
                old_quantity=existing_attachment.quantity,
                new_quantity=new_quantity,
                old_price=existing_attachment.item_price,
                new_price=new_price,
            )

        if dry_run:
            # Determine action type for dry run
            if update_quantity and update_price:
                action_type = ProductActionType.UPDATED_QUANTITY  # Represents "both"
            elif update_quantity:
                action_type = ProductActionType.UPDATED_QUANTITY
            else:
                action_type = ProductActionType.UPDATED_PRICE

            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=action_type,
                product_id=product.id,
                attachment_id=existing_attachment.id,
                old_quantity=existing_attachment.quantity,
                new_quantity=new_quantity if update_quantity else existing_attachment.quantity,
                old_price=existing_attachment.item_price,
                new_price=new_price if update_price else existing_attachment.item_price,
            )

        # Actually update
        try:
            updated_attachment = self.pipedrive_client.update_deal_product_attachment(
                deal_id=deal_id,
                attachment_id=existing_attachment.id,
                item_price=new_price if update_price else None,
                quantity=new_quantity if update_quantity else None,
            )

            if update_quantity and update_price:
                action_type = ProductActionType.UPDATED_QUANTITY
            elif update_quantity:
                action_type = ProductActionType.UPDATED_QUANTITY
            else:
                action_type = ProductActionType.UPDATED_PRICE

            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=action_type,
                product_id=product.id,
                attachment_id=updated_attachment.id,
                old_quantity=existing_attachment.quantity,
                new_quantity=updated_attachment.quantity,
                old_price=existing_attachment.item_price,
                new_price=updated_attachment.item_price,
            )

        except APIError as e:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.ERROR,
                product_id=product.id,
                error_message=f"Failed to update attachment: {str(e)}",
            )

    def _attach_new_product(
        self,
        company: AdditionalCompany,
        product: PipedriveProduct,
        quantity: int,
        price: float,
        deal_id: int,
        dry_run: bool,
    ) -> ProductAction:
        """
        Attach product to deal (new attachment).

        Args:
            company: Company being processed
            product: Product to attach
            quantity: Quantity to attach
            price: Price per unit
            deal_id: Deal ID
            dry_run: If True, preview only

        Returns:
            ProductAction with outcome
        """
        if dry_run:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.ATTACHED_NEW,
                product_id=product.id,
                attachment_id=None,
                new_quantity=quantity,
                new_price=price,
            )

        # Actually attach
        try:
            # Create comments with tracking metadata
            comments = f"AUTO_ATTACHED|company:{company.company_legal_name}"

            attachment = self.pipedrive_client.attach_product_to_deal(
                deal_id=deal_id,
                product_id=product.id,
                item_price=price,
                quantity=quantity,
                comments=comments,
            )

            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.ATTACHED_NEW,
                product_id=product.id,
                attachment_id=attachment.id,
                new_quantity=quantity,
                new_price=price,
            )

        except APIError as e:
            return ProductAction(
                company_name=company.company_legal_name,
                w2_count=company.w2_employee_count,
                action_type=ProductActionType.ERROR,
                product_id=product.id,
                error_message=f"Failed to attach product: {str(e)}",
            )
