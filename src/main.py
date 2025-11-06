# src/main.py
"""
CLI entry point and orchestration.

This is the main entry point for the Additional Companies Product Linker tool.
It handles argument parsing, initialization, and orchestrates the linking process.
"""

import argparse
import sys
import time
import logging
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from .config import Config
from .mongodb_client import MongoDBClient
from .pipedrive_client import PipedriveClient
from .product_linker import ProductLinker
from .reporter import ProgressReporter
from .exceptions import ConfigurationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="MongoDB-Pipedrive Additional Companies Product Linker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview with first 5 submissions
  python -m src.main attach-products --dry-run --limit 5

  # Process first 10 submissions
  python -m src.main attach-products --limit 10

  # Full run with report
  python -m src.main attach-products --report products_report.csv

  # Skip confirmation prompt
  python -m src.main attach-products --no-confirm

  # Verbose output
  python -m src.main attach-products --verbose --limit 5
        """,
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ========================================================================
    # ATTACH-PRODUCTS COMMAND
    # ========================================================================
    attach_parser = subparsers.add_parser(
        "attach-products",
        help="Attach additional companies as products to Pipedrive deals",
    )

    attach_parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Preview changes without actually updating",
    )

    attach_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit number of submissions to process (for testing)",
    )

    attach_parser.add_argument(
        "--report",
        "-r",
        type=str,
        default=None,
        help="Path to save CSV report (e.g., products_report.csv)",
    )

    attach_parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt before processing",
    )

    attach_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    attach_parser.add_argument(
        "--profile",
        "-p",
        type=str,
        default=None,
        help="Configuration profile (standard, conservative, aggressive, migration)",
    )

    args = parser.parse_args()

    # Ensure command is specified
    if not args.command:
        parser.print_help()
        sys.exit(1)

    return args


def attach_products_command(args: argparse.Namespace, config: Config, console: Console) -> int:
    """
    Execute attach-products command.

    Args:
        args: Parsed CLI arguments
        config: Application configuration
        console: Rich console

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize clients
    console.print("[cyan]Connecting to MongoDB...[/cyan]")
    try:
        mongodb_client = MongoDBClient(config)
        submission_count = mongodb_client.get_submission_count()
        console.print(
            f"[green]✓[/green] Connected to MongoDB (submissions: {submission_count:,})\n"
        )
    except Exception as e:
        console.print(
            f"[red]✗[/red] MongoDB connection failed: {str(e)}\n", style="bold red"
        )
        return 1

    console.print("[cyan]Connecting to Pipedrive...[/cyan]")
    try:
        pipedrive_client = PipedriveClient(config)
        console.print("[green]✓[/green] Connected to Pipedrive\n")
    except Exception as e:
        console.print(
            f"[red]✗[/red] Pipedrive connection failed: {str(e)}\n",
            style="bold red",
        )
        mongodb_client.close()
        return 1

    # Fetch submissions with additional companies
    console.print("[cyan]Fetching submissions with additional companies...[/cyan]")
    try:
        submissions = mongodb_client.get_submissions_with_additional_companies(
            limit=args.limit
        )
        console.print(
            f"[green]✓[/green] Found {len(submissions):,} submissions to process\n"
        )
    except Exception as e:
        console.print(
            f"[red]✗[/red] Failed to fetch submissions: {str(e)}\n", style="bold red"
        )
        mongodb_client.close()
        pipedrive_client.close()
        return 1

    if len(submissions) == 0:
        console.print("[yellow]No submissions to process.[/yellow]")
        mongodb_client.close()
        pipedrive_client.close()
        return 0

    # Ask for confirmation unless --no-confirm
    if config.require_confirmation and not args.no_confirm:
        console.print(
            f"[yellow]About to process {len(submissions)} submissions.[/yellow]"
        )
        if args.dry_run:
            console.print("[blue]DRY RUN MODE - No changes will be made[/blue]")
        else:
            console.print("[red]This will modify Pipedrive data.[/red]")

        console.print()
        response = input("Continue? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            console.print("[yellow]Cancelled by user[/yellow]")
            mongodb_client.close()
            pipedrive_client.close()
            return 0
        console.print()

    # Initialize components
    linker = ProductLinker(config, pipedrive_client)
    reporter = ProgressReporter(console, verbose=args.verbose)

    # Process submissions
    console.print("[bold cyan]Processing submissions...[/bold cyan]\n")

    results = []
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Attaching products...", total=len(submissions)
        )

        for i, submission in enumerate(submissions, 1):
            result = linker.link_submission(
                submission,
                dry_run=args.dry_run,
            )
            results.append(result)

            # Display result (pause progress bar)
            progress.stop()
            reporter.display_link_result(result, i, len(submissions), args.dry_run)
            progress.start()

            progress.update(task, advance=1)

            # Rate limit between requests
            if i < len(submissions):
                time.sleep(0.5)

    end_time = time.time()
    duration = end_time - start_time

    # Display summary
    reporter.display_link_summary(
        results=results,
        duration=duration,
        api_calls=pipedrive_client.api_call_count,
        dry_run=args.dry_run,
        report_path=args.report,
    )

    # Export CSV report if requested
    if args.report:
        reporter.export_report_csv(results, args.report)

    # Clean up
    mongodb_client.close()
    pipedrive_client.close()

    # Exit with appropriate code
    from .models import LinkStatus

    failed_count = sum(1 for r in results if r.status == LinkStatus.FAILED_ERROR)
    return 1 if failed_count > 0 else 0


def main() -> None:
    """Main entry point for the tool."""
    console = Console()

    try:
        # Parse arguments
        args = parse_arguments()

        # Display welcome message
        console.print(
            "\n[bold blue]MongoDB-Pipedrive Additional Companies Product Linker[/bold blue]\n"
        )

        if args.dry_run:
            console.print("[yellow]⚠ DRY RUN MODE - No changes will be made[/yellow]\n")

        # Load configuration
        console.print("[cyan]Loading configuration...[/cyan]")
        try:
            # Override profile if specified
            if hasattr(args, "profile") and args.profile:
                import os

                os.environ["CONFIG_PROFILE"] = args.profile

            config = Config.load_from_env()
            console.print("[green]✓[/green] Configuration loaded\n")
        except ConfigurationError as e:
            console.print(
                f"[red]✗[/red] Configuration error: {str(e)}\n", style="bold red"
            )
            console.print(
                "Please ensure your .env file exists and contains all required variables."
            )
            sys.exit(1)

        # Validate configuration
        issues = config.validate()

        # Check for errors
        errors = [i for i in issues if i.level == "ERROR"]
        if errors:
            console.print("[red]✗[/red] Configuration errors found:\n", style="bold red")
            for error in errors:
                console.print(f"  • {error.message}")
            console.print()
            sys.exit(1)

        # Display configuration summary
        reporter = ProgressReporter(console, verbose=False)
        reporter.display_config_summary(config, issues)

        # Route to appropriate command
        if args.command == "attach-products":
            exit_code = attach_products_command(args, config, console)
        else:
            console.print(f"[red]Unknown command: {args.command}[/red]")
            exit_code = 1

        sys.exit(exit_code)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {str(e)}[/red]", style="bold red")
        if hasattr(args, "verbose") and args.verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
