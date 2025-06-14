"""
RSS Error Logger - Comprehensive error logging for RSS feed processing issues.
"""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
import feedparser
from dataclasses import dataclass, asdict
from app.core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class RSSFeedError:
    """Structured RSS feed error data."""
    timestamp: str
    error_type: str
    feed_url: str
    feed_name: Optional[str]
    error_message: str
    error_details: Dict[str, Any]
    stacktrace: Optional[str] = None
    feed_info: Optional[Dict[str, Any]] = None
    problematic_entry: Optional[Dict[str, Any]] = None

@dataclass
class RSSParsingStats:
    """RSS parsing statistics."""
    total_feeds: int
    successful_feeds: int
    failed_feeds: int
    parsing_errors: int
    encoding_errors: int
    missing_link_entries: int
    total_entries_processed: int
    successful_entries: int
    failed_entries: int

class RSSErrorLogger:
    """
    Comprehensive error logger for RSS feed processing.
    Captures detailed error information for debugging and fixing RSS issues.
    """
    
    def __init__(self, log_dir: str = "logs/rss_errors"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped log files
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.error_log_file = self.log_dir / f"rss_errors_{self.timestamp}.json"
        self.stats_log_file = self.log_dir / f"rss_stats_{self.timestamp}.json"
        self.detailed_log_file = self.log_dir / f"rss_detailed_{self.timestamp}.txt"
        
        # Initialize stats
        self.stats = RSSParsingStats(
            total_feeds=0,
            successful_feeds=0,
            failed_feeds=0,
            parsing_errors=0,
            encoding_errors=0,
            missing_link_entries=0,
            total_entries_processed=0,
            successful_entries=0,
            failed_entries=0
        )
        
        # Error storage
        self.errors: List[RSSFeedError] = []
        
        logger.info(f"RSS Error Logger initialized. Logs will be saved to: {self.log_dir}")
    
    def log_feed_parsing_error(
        self,
        feed_url: str,
        error: Exception,
        feed_name: Optional[str] = None,
        parsed_feed: Optional[feedparser.FeedParserDict] = None
    ) -> None:
        """Log a feed parsing error with detailed information."""
        
        # Determine error type
        error_type = "parsing_error"
        if "encoding" in str(error).lower() or "utf-8" in str(error).lower() or "ascii" in str(error).lower():
            error_type = "encoding_error"
            self.stats.encoding_errors += 1
        else:
            self.stats.parsing_errors += 1
        
        # Extract feed info if available
        feed_info = None
        if parsed_feed:
            feed_info = {
                'title': getattr(parsed_feed.feed, 'title', 'N/A'),
                'description': getattr(parsed_feed.feed, 'description', 'N/A'),
                'language': getattr(parsed_feed.feed, 'language', 'N/A'),
                'encoding': getattr(parsed_feed, 'encoding', 'N/A'),
                'version': getattr(parsed_feed, 'version', 'N/A'),
                'bozo': getattr(parsed_feed, 'bozo', False),
                'bozo_exception': str(getattr(parsed_feed, 'bozo_exception', 'None')),
                'entries_count': len(getattr(parsed_feed, 'entries', []))
            }
        
        # Create error record
        error_record = RSSFeedError(
            timestamp=datetime.now().isoformat(),
            error_type=error_type,
            feed_url=feed_url,
            feed_name=feed_name,
            error_message=str(error),
            error_details={
                'exception_type': type(error).__name__,
                'exception_module': type(error).__module__,
            },
            stacktrace=traceback.format_exc(),
            feed_info=feed_info
        )
        
        self.errors.append(error_record)
        self.stats.failed_feeds += 1
        
        # Log to console
        logger.error(f"RSS Feed Error - {error_type}: {feed_url} - {error}")
        
        # Write detailed log
        self._write_detailed_log(error_record)
    
    def log_entry_error(
        self,
        feed_url: str,
        entry: Dict[str, Any],
        error_type: str,
        error_message: str,
        feed_name: Optional[str] = None
    ) -> None:
        """Log an entry-level error (e.g., missing link)."""
        
        if error_type == "missing_link":
            self.stats.missing_link_entries += 1
        
        # Create simplified entry data (avoid circular references)
        entry_data = {
            'title': entry.get('title', 'N/A'),
            'link': entry.get('link', 'N/A'),
            'published': entry.get('published', 'N/A'),
            'author': entry.get('author', 'N/A'),
            'summary': entry.get('summary', 'N/A')[:200] + '...' if entry.get('summary') else 'N/A'
        }
        
        error_record = RSSFeedError(
            timestamp=datetime.now().isoformat(),
            error_type=error_type,
            feed_url=feed_url,
            feed_name=feed_name,
            error_message=error_message,
            error_details={'entry_processing': True},
            problematic_entry=entry_data
        )
        
        self.errors.append(error_record)
        self.stats.failed_entries += 1
        
        # Log to console
        logger.warning(f"RSS Entry Error - {error_type}: {feed_url} - {error_message}")
    
    def log_successful_feed(self, feed_url: str, entries_count: int, feed_name: Optional[str] = None) -> None:
        """Log successful feed processing."""
        self.stats.successful_feeds += 1
        self.stats.total_entries_processed += entries_count
        self.stats.successful_entries += entries_count
        
        logger.info(f"RSS Feed Success: {feed_name or feed_url} - {entries_count} entries")
    
    def increment_feed_count(self) -> None:
        """Increment total feed count."""
        self.stats.total_feeds += 1
    
    def save_logs(self) -> Dict[str, str]:
        """Save all collected logs to files."""
        try:
            # Save errors as JSON
            errors_data = [asdict(error) for error in self.errors]
            with open(self.error_log_file, 'w') as f:
                json.dump(errors_data, f, indent=2, default=str)
            
            # Save stats as JSON
            with open(self.stats_log_file, 'w') as f:
                json.dump(asdict(self.stats), f, indent=2)
            
            # Create summary report
            summary_file = self.log_dir / f"rss_summary_{self.timestamp}.txt"
            with open(summary_file, 'w') as f:
                f.write(self._generate_summary_report())
            
            logger.info(f"RSS logs saved to: {self.log_dir}")
            
            return {
                'errors': str(self.error_log_file),
                'stats': str(self.stats_log_file),
                'detailed': str(self.detailed_log_file),
                'summary': str(summary_file)
            }
            
        except Exception as e:
            logger.error(f"Error saving RSS logs: {e}")
            return {}
    
    def _write_detailed_log(self, error_record: RSSFeedError) -> None:
        """Write detailed error information to text log."""
        try:
            with open(self.detailed_log_file, 'a') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"TIMESTAMP: {error_record.timestamp}\n")
                f.write(f"ERROR TYPE: {error_record.error_type}\n")
                f.write(f"FEED URL: {error_record.feed_url}\n")
                f.write(f"FEED NAME: {error_record.feed_name or 'N/A'}\n")
                f.write(f"ERROR MESSAGE: {error_record.error_message}\n")
                
                if error_record.feed_info:
                    f.write(f"\nFEED INFO:\n")
                    for key, value in error_record.feed_info.items():
                        f.write(f"  {key}: {value}\n")
                
                if error_record.problematic_entry:
                    f.write(f"\nPROBLEMATIC ENTRY:\n")
                    for key, value in error_record.problematic_entry.items():
                        f.write(f"  {key}: {value}\n")
                
                if error_record.stacktrace:
                    f.write(f"\nSTACKTRACE:\n{error_record.stacktrace}\n")
                
                f.write(f"{'='*80}\n")
                
        except Exception as e:
            logger.error(f"Error writing detailed log: {e}")
    
    def _generate_summary_report(self) -> str:
        """Generate a human-readable summary report."""
        report = f"""
RSS Feed Processing Summary Report
Generated: {datetime.now().isoformat()}

OVERALL STATISTICS:
==================
Total Feeds Processed: {self.stats.total_feeds}
Successful Feeds: {self.stats.successful_feeds}
Failed Feeds: {self.stats.failed_feeds}
Success Rate: {(self.stats.successful_feeds / max(self.stats.total_feeds, 1)) * 100:.1f}%

ENTRY STATISTICS:
================
Total Entries Processed: {self.stats.total_entries_processed}
Successful Entries: {self.stats.successful_entries}
Failed Entries: {self.stats.failed_entries}

ERROR BREAKDOWN:
===============
Parsing Errors: {self.stats.parsing_errors}
Encoding Errors: {self.stats.encoding_errors}
Missing Link Entries: {self.stats.missing_link_entries}

DETAILED ERRORS:
===============
"""
        
        # Group errors by type
        error_groups = {}
        for error in self.errors:
            error_type = error.error_type
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(error)
        
        for error_type, errors in error_groups.items():
            report += f"\n{error_type.upper()} ({len(errors)} instances):\n"
            report += f"{'-' * 40}\n"
            
            for error in errors:
                report += f"  • {error.feed_url}\n"
                report += f"    Message: {error.error_message}\n"
                if error.feed_name:
                    report += f"    Feed: {error.feed_name}\n"
                if error.problematic_entry:
                    entry_title = error.problematic_entry.get('title', 'N/A')
                    report += f"    Entry: {entry_title}\n"
                report += "\n"
        
        return report
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return asdict(self.stats)
    
    def get_error_summary(self) -> Dict[str, List[str]]:
        """Get a summary of errors by type."""
        summary = {}
        for error in self.errors:
            error_type = error.error_type
            if error_type not in summary:
                summary[error_type] = []
            summary[error_type].append(f"{error.feed_url}: {error.error_message}")
        return summary