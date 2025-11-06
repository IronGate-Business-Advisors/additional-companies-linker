# src/pipedrive_client.py
"""
Pipedrive API client with rate limiting and retry logic.

This module provides a robust client for interacting with the Pipedrive API,
including product catalog management and deal product attachments.
"""

import requests
import time
from typing import List, Dict, Any, Optional

from .config import Config
from .models import (
    PipedriveProduct,
    DealProductAttachment,
    Deal,
)
from .exceptions import APIError, RateLimitError


class PipedriveClient:
    """
    Client for interacting with Pipedrive API.

    Attributes:
        config: Application configuration
        session: Requests session for connection pooling
        api_call_count: Counter for total API calls made
    """

    def __init__(self, config: Config):
        """
        Initialize client with configuration.

        Args:
            config: Application configuration with API credentials
        """
        self.config = config
        self.session = requests.Session()
        self.api_call_count = 0

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Pipedrive API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            params: Query parameters
            json_data: JSON request body
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed JSON response

        Raises:
            APIError: If request fails after retries
            RateLimitError: If rate limit is exceeded
        """
        if params is None:
            params = {}

        # Add API token to params
        params["api_token"] = self.config.pipedrive_api_key

        url = f"{self.config.base_url}/{endpoint}"

        for attempt in range(max_retries):
            try:
                self.api_call_count += 1

                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=30,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s
                        wait_time = 2**attempt
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RateLimitError(
                            "Rate limit exceeded after retries", status_code=429
                        )

                # Raise for other HTTP errors
                response.raise_for_status()

                return response.json()

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise APIError("Request timeout after retries")

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise APIError(f"Request failed: {str(e)}")

        raise APIError("Unexpected error in request handling")

    # ========================================================================
    # PRODUCT CATALOG OPERATIONS
    # ========================================================================

    def search_product_by_name(
        self, product_name: str, exact_match: bool = True
    ) -> Optional[PipedriveProduct]:
        """
        Search for a product in catalog by name.

        Args:
            product_name: Name to search for
            exact_match: If True, only return exact matches

        Returns:
            PipedriveProduct if found, None otherwise

        Raises:
            APIError: If API call fails
        """
        try:
            # Normalize search term
            search_term = product_name.strip()

            response = self._make_request(
                "GET",
                "products/search",
                params={
                    "term": search_term,
                    "exact_match": 1 if exact_match else 0,
                },
            )

            if not response.get("success", False):
                return None

            items = response.get("data", {}).get("items", [])

            if not items:
                return None

            # Return first exact match
            for item in items:
                item_data = item.get("item", {})
                if exact_match and item_data.get("name", "").strip() == search_term:
                    return self._parse_product(item_data)

            # If no exact match but not requiring it, return first result
            if not exact_match and items:
                return self._parse_product(items[0].get("item", {}))

            return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise APIError(f"Failed to search product: {str(e)}")

    def create_product(
        self,
        name: str,
        code: Optional[str] = None,
        active: bool = True,
        visible_to: int = 3,
    ) -> PipedriveProduct:
        """
        Create a new product in Pipedrive catalog.

        Args:
            name: Product name
            code: Optional product code
            active: Whether product is active
            visible_to: Visibility setting (1=owner, 3=everyone, 5=owner+followers)

        Returns:
            Created PipedriveProduct

        Raises:
            APIError: If creation fails
        """
        product_data: Dict[str, Any] = {
            "name": name[:255],  # Truncate if too long
            "active_flag": active,
            "visible_to": visible_to,
        }

        if code:
            product_data["code"] = code

        response = self._make_request("POST", "products", json_data=product_data)

        if not response.get("success", False):
            raise APIError(f"Failed to create product: {name}")

        return self._parse_product(response.get("data", {}))

    def get_product_by_id(self, product_id: int) -> Optional[PipedriveProduct]:
        """
        Fetch a product by ID.

        Args:
            product_id: Product ID to fetch

        Returns:
            PipedriveProduct or None if not found

        Raises:
            APIError: If API call fails (except 404)
        """
        try:
            response = self._make_request("GET", f"products/{product_id}")

            if not response.get("success", False):
                return None

            product_data = response.get("data")
            if not product_data:
                return None

            return self._parse_product(product_data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise APIError(f"Failed to fetch product {product_id}: {str(e)}")

    def update_product(
        self,
        product_id: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> PipedriveProduct:
        """
        Update a product in catalog.

        Args:
            product_id: Product ID to update
            name: New product name (optional)
            code: New product code (optional)
            active: New active status (optional)

        Returns:
            Updated PipedriveProduct

        Raises:
            APIError: If update fails
        """
        update_data: Dict[str, Any] = {}

        if name is not None:
            update_data["name"] = name[:255]

        if code is not None:
            update_data["code"] = code

        if active is not None:
            update_data["active_flag"] = active

        response = self._make_request(
            "PUT", f"products/{product_id}", json_data=update_data
        )

        if not response.get("success", False):
            raise APIError(f"Failed to update product {product_id}")

        return self._parse_product(response.get("data", {}))

    # ========================================================================
    # DEAL OPERATIONS
    # ========================================================================

    def get_deal_by_id(self, deal_id: int) -> Optional[Deal]:
        """
        Fetch a deal by ID.

        Args:
            deal_id: Deal ID to fetch

        Returns:
            Deal or None if not found

        Raises:
            APIError: If API call fails (except 404)
        """
        try:
            response = self._make_request("GET", f"deals/{deal_id}")

            if not response.get("success", False):
                return None

            deal_data = response.get("data")
            if not deal_data:
                return None

            return self._parse_deal(deal_data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise APIError(f"Failed to fetch deal {deal_id}: {str(e)}")

    # ========================================================================
    # DEAL PRODUCT ATTACHMENT OPERATIONS
    # ========================================================================

    def get_deal_products(self, deal_id: int) -> List[DealProductAttachment]:
        """
        Get all products attached to a deal.

        Args:
            deal_id: Deal ID

        Returns:
            List of DealProductAttachment objects

        Raises:
            APIError: If API call fails
        """
        try:
            response = self._make_request("GET", f"deals/{deal_id}/products")

            if not response.get("success", False):
                return []

            products_data = response.get("data", []) or []

            attachments = []
            for product_data in products_data:
                attachments.append(self._parse_deal_product_attachment(product_data))

            return attachments

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise APIError(
                f"Failed to fetch products for deal {deal_id}: {str(e)}"
            )

    def attach_product_to_deal(
        self,
        deal_id: int,
        product_id: int,
        item_price: float,
        quantity: int,
        comments: Optional[str] = None,
    ) -> DealProductAttachment:
        """
        Attach a product to a deal.

        Args:
            deal_id: Deal ID
            product_id: Product ID to attach
            item_price: Price per unit
            quantity: Number of units
            comments: Optional comments/notes

        Returns:
            Created DealProductAttachment

        Raises:
            APIError: If attachment fails
        """
        attachment_data: Dict[str, Any] = {
            "product_id": product_id,
            "item_price": item_price,
            "quantity": quantity,
            "discount": 0,
            "duration": 1,
            "enabled_flag": True,
        }

        if comments:
            attachment_data["comments"] = comments

        response = self._make_request(
            "POST", f"deals/{deal_id}/products", json_data=attachment_data
        )

        if not response.get("success", False):
            raise APIError(
                f"Failed to attach product {product_id} to deal {deal_id}"
            )

        return self._parse_deal_product_attachment(response.get("data", {}))

    def update_deal_product_attachment(
        self,
        deal_id: int,
        attachment_id: int,
        item_price: Optional[float] = None,
        quantity: Optional[int] = None,
        comments: Optional[str] = None,
    ) -> DealProductAttachment:
        """
        Update an existing product attachment on a deal.

        Args:
            deal_id: Deal ID
            attachment_id: Attachment ID to update
            item_price: New price per unit (optional)
            quantity: New quantity (optional)
            comments: New comments (optional)

        Returns:
            Updated DealProductAttachment

        Raises:
            APIError: If update fails
        """
        update_data: Dict[str, Any] = {}

        if item_price is not None:
            update_data["item_price"] = item_price

        if quantity is not None:
            update_data["quantity"] = quantity

        if comments is not None:
            update_data["comments"] = comments

        response = self._make_request(
            "PUT", f"deals/{deal_id}/products/{attachment_id}", json_data=update_data
        )

        if not response.get("success", False):
            raise APIError(
                f"Failed to update attachment {attachment_id} on deal {deal_id}"
            )

        return self._parse_deal_product_attachment(response.get("data", {}))

    def delete_deal_product_attachment(
        self, deal_id: int, attachment_id: int
    ) -> bool:
        """
        Delete a product attachment from a deal.

        Args:
            deal_id: Deal ID
            attachment_id: Attachment ID to delete

        Returns:
            True if deleted successfully

        Raises:
            APIError: If deletion fails
        """
        response = self._make_request(
            "DELETE", f"deals/{deal_id}/products/{attachment_id}"
        )

        return response.get("success", False)

    # ========================================================================
    # PARSING HELPERS
    # ========================================================================

    def _parse_product(self, raw_product: Dict[str, Any]) -> PipedriveProduct:
        """Parse raw API response into PipedriveProduct model."""
        return PipedriveProduct(
            id=raw_product["id"],
            name=raw_product.get("name", ""),
            code=raw_product.get("code"),
            active_flag=raw_product.get("active_flag", True),
            prices=raw_product.get("prices", []),
        )

    def _parse_deal(self, raw_deal: Dict[str, Any]) -> Deal:
        """Parse raw API response into Deal model."""
        return Deal(
            id=raw_deal["id"],
            title=raw_deal.get("title", ""),
            value=raw_deal.get("value"),
            stage_id=raw_deal.get("stage_id", 0),
            pipeline_id=raw_deal.get("pipeline_id", 0),
            org_id=raw_deal.get("org_id"),
        )

    def _parse_deal_product_attachment(
        self, raw_attachment: Dict[str, Any]
    ) -> DealProductAttachment:
        """Parse raw API response into DealProductAttachment model."""
        return DealProductAttachment(
            id=raw_attachment["id"],
            product_id=raw_attachment.get("product_id", 0),
            deal_id=raw_attachment.get("deal_id", 0),
            item_price=float(raw_attachment.get("item_price", 0)),
            quantity=int(raw_attachment.get("quantity", 0)),
            sum=float(raw_attachment.get("sum", 0)),
            name=raw_attachment.get("name", ""),
            comments=raw_attachment.get("comments"),
        )

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()
