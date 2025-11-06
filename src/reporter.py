# src/reporter.py
"""
Progress reporting and summary display using Rich.

This module handles all console output and CSV report generation.
"""

import csv
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .models import (
    LinkResult,
    LinkStatus,
    ProductActionType,
    ConfigIssue,
)
from .config import Config


class ProgressReporter:
    """
    Handles progress display and reporting using Rich.

    Attributes:
        console: Rich console for output
        verbose: Whether to show verbose output
    """

    def __init__(self, console: Console, verbose: bool = False):
        """
        Initialize reporter.

        Args:
            console: Rich console instance
            verbose: Enable verbose logging
        """
        self.console = console
        self.verbose = verbose

    def display_config_summary(
        self, config: Config, issues: List[ConfigIssue]
    ) -> None:
        """
        Display configuration summary with validation results.

        Args:
            config: Application configuration
            issues: List of configuration issues
        """
        summary_text = config.get_summary()

        # Add validation results
        summary_lines = summary_text.split("\n")
        summary_lines.append("")
        summary_lines.append("Validation:")

        if not issues:
            summary_lines.append("  ✓ All settings valid")
        else:
            errors = [i for i in issues if i.level == "ERROR"]
            warnings = [i for i in issues if i.level == "WARNING"]

            if errors:
                summary_lines.append(f"  ✗ {len(errors)} error(s):")
                for error in errors:
                    summary_lines.append(f"    • {error.message}")

            if warnings:
                summary_lines.append(f"  ⚠ {len(warnings)} warning(s):")
                for warning in warnings:
                    summary_lines.append(f"    • {warning.message}")

        summary_text = "\n".join(summary_lines)

        panel = Panel(summary_text, title="Configuration", border_style="cyan")
        self.console.print(panel)
        self.console.print()

    def display_link_result(
        self, result: LinkResult, index: int, total: int, dry_run: bool
    ) -> None:
        """
        Display individual link result.

        Args:
            result: Link result to display
            index: Current index (1-based)
            total: Total number of submissions
            dry_run: Whether this is a dry run
        """
        # Header
        deal_str = f" (Deal #{result.deal_id})" if result.deal_id else ""
        header = f"[cyan][{index}/{total}] Submission {result.submission_id[:12]}...{deal_str}[/cyan]"
        self.console.print(header)

        # Display based on status
        if result.status == LinkStatus.SUCCESS:
            self.console.print(
                f"  Companies Processed: {result.companies_processed}"
            )
            self.console.print(f"  Total Value Added: ${result.total_value_added:.2f}")

            # Show action summary
            self.console.print(
                f"    Products Created: {result.products_created}"
            )
            self.console.print(f"    Products Found: {result.products_found}")
            self.console.print(
                f"    Attachments Created: {result.attachments_created}"
            )
            self.console.print(
                f"    Attachments Updated: {result.attachments_updated}"
            )

            if self.verbose:
                # Show detailed actions
                for action in result.actions:
                    self._display_action(action)

            if dry_run:
                self.console.print(
                    "  [blue]DRY RUN:[/blue] Would make these changes"
                )
            else:
                self.console.print("  [green]✓[/green] Processed successfully")

        elif result.status == LinkStatus.SKIPPED:
            self.console.print(
                "  [blue]⏭[/blue] All products already attached with correct values"
            )

        elif result.status == LinkStatus.NO_DEAL_ID:
            self.console.print("  [yellow]⚠[/yellow] Skipped: No dealId")

        elif result.status == LinkStatus.NO_COMPANIES:
            self.console.print("  [yellow]⚠[/yellow] Skipped: No companies to process")

        elif result.status == LinkStatus.ORPHANED:
            self.console.print(
                f"  [yellow]⚠[/yellow] Orphaned: Deal #{result.deal_id} not found"
            )

        elif result.status == LinkStatus.FAILED_ERROR:
            self.console.print(f"  [red]✗[/red] Failed: {result.error_message}")

        self.console.print()  # Blank line

    def _display_action(self, action) -> None:
        """Display detailed action information."""
        indent = "      "

        if action.action_type == ProductActionType.CREATED_CATALOG:
            self.console.print(
                f"{indent}• Created product: {action.company_name} (ID: {action.product_id})"
            )

        elif action.action_type == ProductActionType.ATTACHED_NEW:
            self.console.print(
                f"{indent}• Attached: {action.company_name} (qty: {action.new_quantity}, price: ${action.new_price})"
            )

        elif action.action_type == ProductActionType.UPDATED_QUANTITY:
            self.console.print(
                f"{indent}• Updated: {action.company_name} (qty: {action.old_quantity} → {action.new_quantity})"
            )

        elif action.action_type == ProductActionType.UPDATED_PRICE:
            self.console.print(
                f"{indent}• Updated: {action.company_name} (price: ${action.old_price} → ${action.new_price})"
            )

        elif action.action_type == ProductActionType.SKIPPED_EXISTS:
            self.console.print(
                f"{indent}• Skipped: {action.company_name} (already correct)"
            )

        elif action.action_type == ProductActionType.ERROR:
            self.console.print(
                f"{indent}• Error: {action.company_name} - {action.error_message}"
            )

    def display_link_summary(
        self,
        results: List[LinkResult],
        duration: float,
        api_calls: int,
        dry_run: bool,
        report_path: Optional[str] = None,
    ) -> None:
        """
        Display final link summary with Rich Table.

        Args:
            results: List of all link results
            duration: Total time elapsed in seconds
            api_calls: Total number of API calls made
            dry_run: Whether this was a dry run
            report_path: Path to generated CSV report (if any)
        """
        stats = self._calculate_statistics(results)

        # Header
        if dry_run:
            header_text = "Product Attachment Summary\n(DRY RUN MODE)"
        else:
            header_text = "Product Attachment Summary"

        header = Panel(header_text, style="bold blue", expand=False)
        self.console.print()
        self.console.print(header)
        self.console.print()

        # Summary table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", width=50)
        table.add_column("Count", justify="right", style="bold white")

        table.add_row("Total Submissions Processed", str(stats["total"]))
        table.add_row("Total Companies Processed", str(stats["companies_processed"]))
        table.add_row(
            "[green]✓[/green] Successfully Processed",
            f"[green]{stats['success']}[/green]",
        )
        table.add_row(
            "[blue]⏭[/blue] Skipped (Already Correct)",
            f"[blue]{stats['skipped']}[/blue]",
        )
        table.add_row(
            "[yellow]⚠[/yellow] No Deal ID", f"[yellow]{stats['no_deal_id']}[/yellow]"
        )
        table.add_row(
            "[yellow]⚠[/yellow] No Companies",
            f"[yellow]{stats['no_companies']}[/yellow]",
        )
        table.add_row(
            "[yellow]⚠[/yellow] Orphaned Deals",
            f"[yellow]{stats['orphaned']}[/yellow]",
        )
        table.add_row("[red]✗[/red] Errors", f"[red]{stats['failed']}[/red]")

        table.add_section()
        table.add_row("Products Created (new to catalog)", str(stats["products_created"]))
        table.add_row("Products Found (existing)", str(stats["products_found"]))
        table.add_row("Attachments Created (new)", str(stats["attachments_created"]))
        table.add_row("Attachments Updated", str(stats["attachments_updated"]))
        table.add_row("Attachments Skipped", str(stats["attachments_skipped"]))

        table.add_section()
        table.add_row(
            "Total Value Added",
            f"${stats['total_value']:,.2f}",
        )

        table.add_section()
        table.add_row("Total API Calls Made", str(api_calls))

        # Format duration
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        table.add_row("Total Time Elapsed", duration_str)

        if results:
            avg_time = duration / len(results)
            table.add_row("Average Time per Submission", f"{avg_time:.2f}s")

        self.console.print(table)
        self.console.print()

        # Final message
        if dry_run:
            self.console.print(
                "[blue]ℹ[/blue] DRY RUN MODE - No actual changes were made",
                style="bold",
            )
            self.console.print("  Run without --dry-run flag to apply changes")
        else:
            if stats["failed"] == 0:
                self.console.print(
                    "[green]✓[/green] Processing completed successfully!", style="bold"
                )
            else:
                self.console.print(
                    "[yellow]⚠[/yellow] Processing completed with some errors",
                    style="bold",
                )

        if report_path:
            self.console.print(f"  Report saved to: {report_path}")

        self.console.print()

    def _calculate_statistics(self, results: List[LinkResult]) -> dict:
        """Calculate statistics from link results."""
        stats = {
            "total": len(results),
            "companies_processed": sum(r.companies_processed for r in results),
            "success": sum(1 for r in results if r.status == LinkStatus.SUCCESS),
            "skipped": sum(1 for r in results if r.status == LinkStatus.SKIPPED),
            "no_deal_id": sum(1 for r in results if r.status == LinkStatus.NO_DEAL_ID),
            "no_companies": sum(
                1 for r in results if r.status == LinkStatus.NO_COMPANIES
            ),
            "orphaned": sum(1 for r in results if r.status == LinkStatus.ORPHANED),
            "failed": sum(1 for r in results if r.status == LinkStatus.FAILED_ERROR),
            "products_created": sum(r.products_created for r in results),
            "products_found": sum(r.products_found for r in results),
            "attachments_created": sum(r.attachments_created for r in results),
            "attachments_updated": sum(r.attachments_updated for r in results),
            "attachments_skipped": sum(r.attachments_skipped for r in results),
            "total_value": sum(r.total_value_added for r in results),
        }

        return stats

    def export_report_csv(self, results: List[LinkResult], output_path: str) -> None:
        """
        Export link results to CSV.

        Args:
            results: Link results
            output_path: Path to save CSV file
        """
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "submission_id",
                    "deal_id",
                    "status",
                    "companies_processed",
                    "products_created",
                    "products_found",
                    "attachments_created",
                    "attachments_updated",
                    "attachments_skipped",
                    "total_value_added",
                    "error_message",
                ]
            )

            for result in results:
                writer.writerow(
                    [
                        result.submission_id,
                        result.deal_id or "",
                        result.status.value,
                        result.companies_processed,
                        result.products_created,
                        result.products_found,
                        result.attachments_created,
                        result.attachments_updated,
                        result.attachments_skipped,
                        f"{result.total_value_added:.2f}",
                        result.error_message or "",
                    ]
                )

        self.console.print(f"[green]✓[/green] CSV report saved to: {output_path}")
