# src/mongodb_client.py
"""
MongoDB client for submission CRUD operations.

This module provides a clean interface for interacting with MongoDB
submissions, including fetching and parsing additional companies data.
"""

from typing import List, Optional, Dict, Any
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .config import Config
from .models import Submission, AdditionalCompany, ProcessCompaniesMode
from .exceptions import MongoDBError


class MongoDBClient:
    """
    Client for interacting with MongoDB submissions.

    Attributes:
        config: Application configuration
        client: MongoDB client instance
        db: Database reference
        collection: Collection reference
    """

    def __init__(self, config: Config):
        """
        Initialize MongoDB client.

        Args:
            config: Application configuration

        Raises:
            MongoDBError: If connection fails
        """
        self.config = config
        self.client: MongoClient[Dict[str, Any]]

        try:
            self.client = MongoClient(config.mongodb_connection_string)
            self.db = self.client[config.mongodb_database]
            self.collection = self.db[config.mongodb_collection]
            # Test connection
            self.client.server_info()
        except PyMongoError as e:
            raise MongoDBError(f"Failed to connect to MongoDB: {str(e)}")

    def get_submission_count(self) -> int:
        """
        Get total count of submissions in collection.

        Returns:
            Total number of submissions

        Raises:
            MongoDBError: If query fails
        """
        try:
            return self.collection.count_documents({})
        except PyMongoError as e:
            raise MongoDBError(f"Failed to count submissions: {str(e)}")

    def get_submissions_with_deal_id(
        self, limit: Optional[int] = None
    ) -> List[Submission]:
        """
        Fetch submissions that have dealId.

        Args:
            limit: Optional limit on number of submissions to fetch

        Returns:
            List of Submission objects

        Raises:
            MongoDBError: If query fails
        """
        try:
            query = {"dealId": {"$exists": True, "$ne": None}}

            cursor = self.collection.find(query)
            if limit:
                cursor = cursor.limit(limit)

            submissions = []
            for doc in cursor:
                submission = self._parse_submission(doc)
                submissions.append(submission)

            return submissions

        except PyMongoError as e:
            raise MongoDBError(f"Failed to fetch submissions: {str(e)}")

    def get_submissions_with_additional_companies(
        self, limit: Optional[int] = None
    ) -> List[Submission]:
        """
        Fetch submissions that have dealId AND additional companies.

        Args:
            limit: Optional limit on number of submissions to fetch

        Returns:
            List of Submission objects with additional companies

        Raises:
            MongoDBError: If query fails
        """
        try:
            query = {
                "dealId": {"$exists": True, "$ne": None},
                "data.additionalBusinesses": {"$exists": True, "$ne": []},
            }

            cursor = self.collection.find(query)
            if limit:
                cursor = cursor.limit(limit)

            submissions = []
            for doc in cursor:
                submission = self._parse_submission(doc)
                # Only include if actually has companies based on config
                if self._should_include_submission(submission):
                    submissions.append(submission)

            return submissions

        except PyMongoError as e:
            raise MongoDBError(f"Failed to fetch submissions: {str(e)}")

    def _should_include_submission(self, submission: Submission) -> bool:
        """
        Check if submission should be included based on configuration.

        Args:
            submission: Submission to check

        Returns:
            True if submission should be processed
        """
        process_mode = self.config.process_companies

        if process_mode == ProcessCompaniesMode.ADDITIONAL_ONLY:
            return len(submission.additional_companies) > 0

        elif process_mode == ProcessCompaniesMode.PRIMARY_ONLY:
            return submission.primary_company is not None

        elif process_mode == ProcessCompaniesMode.BOTH:
            return (
                submission.primary_company is not None
                or len(submission.additional_companies) > 0
            )

        return False

    def _parse_submission(self, doc: Dict[str, Any]) -> Submission:
        """
        Parse MongoDB document into Submission model.

        Args:
            doc: Raw MongoDB document

        Returns:
            Submission object

        Raises:
            MongoDBError: If document structure is invalid
        """
        try:
            submission_id = str(doc["_id"])

            # Extract nested fields
            data = doc.get("data", {})

            # Extract email
            email = data.get("email", "").lower().strip()

            # Extract dealId
            deal_id = doc.get("dealId")
            if deal_id is not None:
                try:
                    deal_id = int(deal_id)
                except (ValueError, TypeError):
                    deal_id = None

            # Parse primary company
            primary_company = self._parse_primary_company(data)

            # Parse additional companies
            additional_companies = self._parse_additional_companies(data)

            return Submission(
                id=submission_id,
                deal_id=deal_id,
                primary_company=primary_company,
                additional_companies=additional_companies,
                email=email,
                raw_data=doc,
            )

        except KeyError as e:
            raise MongoDBError(
                f"Invalid submission document structure, missing key: {str(e)}"
            )

    def _parse_primary_company(
        self, data: Dict[str, Any]
    ) -> Optional[AdditionalCompany]:
        """
        Parse primary company from submission data.

        Args:
            data: Submission data dictionary

        Returns:
            AdditionalCompany object or None if not present
        """
        primary_company_data = data.get("primaryCompany", {})

        if not primary_company_data:
            return None

        company_name = primary_company_data.get("companyLegalName", "").strip()

        if not company_name:
            return None

        # Extract W2 count
        w2_count = None
        w2_raw = primary_company_data.get("w2EmployeeCount")
        if w2_raw is not None:
            try:
                w2_count = int(w2_raw)
            except (ValueError, TypeError):
                pass

        return AdditionalCompany(
            company_legal_name=company_name,
            w2_employee_count=w2_count,
            raw_data=primary_company_data,
        )

    def _parse_additional_companies(
        self, data: Dict[str, Any]
    ) -> List[AdditionalCompany]:
        """
        Parse additional companies array from submission data.

        Args:
            data: Submission data dictionary

        Returns:
            List of AdditionalCompany objects
        """
        additional_companies_data = data.get("additionalCompanies", [])

        if not additional_companies_data or not isinstance(
            additional_companies_data, list
        ):
            return []

        companies: List[AdditionalCompany] = []

        for company_data in additional_companies_data:
            if not isinstance(company_data, dict):
                continue

            company_name = company_data.get("companyLegalName", "").strip()

            if not company_name:
                continue

            # Extract W2 count
            w2_count = None
            w2_raw = company_data.get("w2EmployeeCount")
            if w2_raw is not None:
                try:
                    w2_count = int(w2_raw)
                except (ValueError, TypeError):
                    pass

            companies.append(
                AdditionalCompany(
                    company_legal_name=company_name,
                    w2_employee_count=w2_count,
                    raw_data=company_data,
                )
            )

        return companies

    def close(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
