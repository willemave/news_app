#!/usr/bin/env python3
"""
Script to dump and pretty-print database state.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add the parent directory to the path so we can import from app
sys.path.append(str(Path(__file__).parent.parent))

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.core.db import get_db
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ProcessingTask


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max_length with ellipsis."""
    if not text:
        return ""
    return text[:max_length] + "..." if len(text) > max_length else text


def format_json_field(data: dict[Any, Any], max_length: int = 100) -> str:
    """Format JSON field for table display."""
    if not data:
        return ""

    json_str = json.dumps(data, separators=(",", ":"))
    return truncate_text(json_str, max_length)


def dump_content_table(console: Console) -> None:
    """Dump and display Content table."""
    with get_db() as db:
        contents = db.query(Content).order_by(Content.created_at.desc()).all()

        if not contents:
            console.print("[yellow]No content records found.[/yellow]")
            return

        # Create summary statistics
        total_count = len(contents)
        status_counts = {}
        type_counts = {}

        for content in contents:
            status_counts[content.status] = status_counts.get(content.status, 0) + 1
            type_counts[content.content_type] = type_counts.get(content.content_type, 0) + 1

        # Display summary
        summary_table = Table(title="Content Summary", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")

        summary_table.add_row("Total Records", str(total_count))
        summary_table.add_row("", "")  # Separator

        for status, count in status_counts.items():
            summary_table.add_row(f"Status: {status}", str(count))

        summary_table.add_row("", "")  # Separator

        for content_type, count in type_counts.items():
            summary_table.add_row(f"Type: {content_type}", str(count))

        console.print(summary_table)
        console.print()

        # Display detailed content table
        content_table = Table(
            title=f"Content Records (Latest {min(20, total_count)})", show_header=True
        )
        content_table.add_column("ID", width=6)
        content_table.add_column("Type", width=8)
        content_table.add_column("Status", width=10)
        content_table.add_column("Title", width=40)
        content_table.add_column("URL", width=50)
        content_table.add_column("Checked Out", width=12)
        content_table.add_column("Retries", width=8)
        content_table.add_column("Created", width=12)
        content_table.add_column("Metadata", width=30)

        # Show latest 20 records
        for content in contents[:20]:
            # Format status with color
            status_style = {
                ContentStatus.NEW.value: "blue",
                ContentStatus.PROCESSING.value: "yellow",
                ContentStatus.COMPLETED.value: "green",
                ContentStatus.FAILED.value: "red",
                ContentStatus.SKIPPED.value: "dim",
            }.get(content.status, "white")

            # Format type with color
            type_style = {
                ContentType.ARTICLE.value: "cyan",
                ContentType.PODCAST.value: "magenta",
            }.get(content.content_type, "white")

            checkout_info = "Yes" if content.checked_out_by else "No"
            created_str = content.created_at.strftime("%m/%d %H:%M") if content.created_at else ""

            content_table.add_row(
                str(content.id),
                f"[{type_style}]{content.content_type}[/{type_style}]",
                f"[{status_style}]{content.status}[/{status_style}]",
                truncate_text(content.title or "", 40),
                truncate_text(content.url, 50),
                checkout_info,
                str(content.retry_count),
                created_str,
                format_json_field(content.content_metadata, 30),
            )

        console.print(content_table)


def dump_processing_tasks_table(console: Console) -> None:
    """Dump and display ProcessingTask table."""
    with get_db() as db:
        tasks = db.query(ProcessingTask).order_by(ProcessingTask.created_at.desc()).all()

        if not tasks:
            console.print("[yellow]No processing task records found.[/yellow]")
            return

        # Create summary statistics
        total_count = len(tasks)
        status_counts = {}
        type_counts = {}

        for task in tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
            type_counts[task.task_type] = type_counts.get(task.task_type, 0) + 1

        # Display summary
        summary_table = Table(title="Processing Tasks Summary", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")

        summary_table.add_row("Total Tasks", str(total_count))
        summary_table.add_row("", "")  # Separator

        for status, count in status_counts.items():
            summary_table.add_row(f"Status: {status}", str(count))

        summary_table.add_row("", "")  # Separator

        for task_type, count in type_counts.items():
            summary_table.add_row(f"Type: {task_type}", str(count))

        console.print(summary_table)
        console.print()

        # Display detailed tasks table
        tasks_table = Table(
            title=f"Processing Tasks (Latest {min(20, total_count)})", show_header=True
        )
        tasks_table.add_column("ID", width=6)
        tasks_table.add_column("Type", width=15)
        tasks_table.add_column("Status", width=10)
        tasks_table.add_column("Content ID", width=10)
        tasks_table.add_column("Retries", width=8)
        tasks_table.add_column("Created", width=12)
        tasks_table.add_column("Started", width=12)
        tasks_table.add_column("Completed", width=12)
        tasks_table.add_column("Error", width=30)

        # Show latest 20 records
        for task in tasks[:20]:
            # Format status with color
            status_style = {
                "pending": "blue",
                "running": "yellow",
                "completed": "green",
                "failed": "red",
            }.get(task.status, "white")

            created_str = task.created_at.strftime("%m/%d %H:%M") if task.created_at else ""
            started_str = task.started_at.strftime("%m/%d %H:%M") if task.started_at else ""
            completed_str = task.completed_at.strftime("%m/%d %H:%M") if task.completed_at else ""

            tasks_table.add_row(
                str(task.id),
                task.task_type,
                f"[{status_style}]{task.status}[/{status_style}]",
                str(task.content_id) if task.content_id else "",
                str(task.retry_count),
                created_str,
                started_str,
                completed_str,
                truncate_text(task.error_message or "", 30),
            )

        console.print(tasks_table)


def show_detailed_record(console: Console, table_name: str, record_id: int) -> None:
    """Show detailed view of a specific record."""
    with get_db() as db:
        if table_name.lower() == "content":
            record = db.query(Content).filter(Content.id == record_id).first()
            if not record:
                console.print(f"[red]Content record with ID {record_id} not found.[/red]")
                return

            # Display detailed content
            console.print(Panel(f"[bold]Content Record #{record.id}[/bold]"))

            details = [
                f"[cyan]Type:[/cyan] {record.content_type}",
                f"[cyan]Status:[/cyan] {record.status}",
                f"[cyan]Title:[/cyan] {record.title or 'N/A'}",
                f"[cyan]URL:[/cyan] {record.url}",
                f"[cyan]Retry Count:[/cyan] {record.retry_count}",
                f"[cyan]Checked Out By:[/cyan] {record.checked_out_by or 'None'}",
                f"[cyan]Checked Out At:[/cyan] {record.checked_out_at or 'None'}",
                f"[cyan]Created At:[/cyan] {record.created_at}",
                f"[cyan]Updated At:[/cyan] {record.updated_at}",
                f"[cyan]Processed At:[/cyan] {record.processed_at or 'None'}",
            ]

            if record.error_message:
                details.append(f"[cyan]Error Message:[/cyan] {record.error_message}")

            for detail in details:
                console.print(detail)

            if record.content_metadata:
                console.print("\n[cyan]Metadata:[/cyan]")
                console.print(JSON.from_data(record.content_metadata))

        elif table_name.lower() == "task":
            record = db.query(ProcessingTask).filter(ProcessingTask.id == record_id).first()
            if not record:
                console.print(f"[red]ProcessingTask record with ID {record_id} not found.[/red]")
                return

            # Display detailed task
            console.print(Panel(f"[bold]Processing Task #{record.id}[/bold]"))

            details = [
                f"[cyan]Task Type:[/cyan] {record.task_type}",
                f"[cyan]Status:[/cyan] {record.status}",
                f"[cyan]Content ID:[/cyan] {record.content_id or 'None'}",
                f"[cyan]Retry Count:[/cyan] {record.retry_count}",
                f"[cyan]Created At:[/cyan] {record.created_at}",
                f"[cyan]Started At:[/cyan] {record.started_at or 'None'}",
                f"[cyan]Completed At:[/cyan] {record.completed_at or 'None'}",
            ]

            if record.error_message:
                details.append(f"[cyan]Error Message:[/cyan] {record.error_message}")

            for detail in details:
                console.print(detail)

            if record.payload:
                console.print("\n[cyan]Payload:[/cyan]")
                console.print(JSON.from_data(record.payload))


def main():
    """Main function to dump database state."""
    console = Console()

    # Header
    console.print(
        Panel(
            Text("Database State Dump", justify="center", style="bold blue"),
            subtitle=f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )
    )

    if len(sys.argv) > 1:
        # Detailed view mode
        if len(sys.argv) != 3:
            console.print(
                "[red]Usage for detailed view: python dump_database.py <table> <id>[/red]"
            )
            console.print("[yellow]Tables: content, task[/yellow]")
            sys.exit(1)

        table_name = sys.argv[1]
        try:
            record_id = int(sys.argv[2])
        except ValueError:
            console.print("[red]Record ID must be an integer.[/red]")
            sys.exit(1)

        show_detailed_record(console, table_name, record_id)
    else:
        # Overview mode
        dump_content_table(console)
        console.print()
        dump_processing_tasks_table(console)

        console.print(
            "\n[dim]Tip: Use 'python dump_database.py content <id>' or "
            "'python dump_database.py task <id>' for detailed view[/dim]"
        )


if __name__ == "__main__":
    main()
