"""
Generic Error Logger - Simple, universal error logging with full context capture.
"""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict

from app.core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ErrorContext:
    """Structured error context data."""
    timestamp: str
    component: str
    operation: Optional[str]
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None
    http_details: Optional[Dict[str, Any]] = None
    item_id: Optional[Union[str, int]] = None

class GenericErrorLogger:
    """
    Simple, universal error logger with full context capture.
    Designed to replace complex RSS-specific logger with better debugging info.
    """
    
    def __init__(self, component: str, log_dir: str = "logs/errors"):
        self.component = component
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{component}_{timestamp}.jsonl"
        
        logger.info(f"Generic error logger initialized for {component}. Logs: {self.log_file}")
    
    def log_error(
        self,
        error: Exception,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_response: Optional[Any] = None,
        item_id: Optional[Union[str, int]] = None
    ) -> None:
        """Log error with full context."""
        
        # Extract HTTP details if response provided
        http_details = None
        if http_response:
            http_details = self._extract_http_details(http_response)
        
        error_context = ErrorContext(
            timestamp=datetime.now().isoformat(),
            component=self.component,
            operation=operation,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            context_data=context,
            http_details=http_details,
            item_id=item_id
        )
        
        self._write_log(error_context)
        
        # Also log to console for immediate visibility
        operation_str = f" during {operation}" if operation else ""
        item_str = f" (item: {item_id})" if item_id else ""
        logger.error(f"{self.component} error{operation_str}{item_str}: {error}")
    
    def log_http_error(
        self,
        url: str,
        response: Optional[Any] = None,
        error: Optional[Exception] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log HTTP-specific errors with response details."""
        
        # Build context with URL
        full_context = {"url": url}
        if context:
            full_context.update(context)
        
        # Use provided error or create a generic one
        if not error:
            status_code = getattr(response, 'status_code', 'unknown')
            error = Exception(f"HTTP error for {url} (status: {status_code})")
        
        self.log_error(
            error=error,
            operation=operation or "http_request",
            context=full_context,
            http_response=response
        )
    
    def log_processing_error(
        self,
        item_id: Union[str, int],
        error: Exception,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log processing errors with item context."""
        
        self.log_error(
            error=error,
            operation=operation or "content_processing",
            context=context,
            item_id=item_id
        )
    
    def log_feed_error(
        self,
        feed_url: str,
        error: Exception,
        feed_name: Optional[str] = None,
        entries_processed: Optional[int] = None,
        operation: Optional[str] = None
    ) -> None:
        """Log feed-specific errors (for RSS/feed processing)."""
        
        context = {
            "feed_url": feed_url,
            "feed_name": feed_name,
            "entries_processed": entries_processed
        }
        
        self.log_error(
            error=error,
            operation=operation or "feed_processing",
            context=context
        )
    
    def _extract_http_details(self, response: Any) -> Dict[str, Any]:
        """Extract useful details from HTTP response object."""
        details = {}
        
        try:
            # Handle different response object types
            if hasattr(response, 'status_code'):
                details['status_code'] = response.status_code
            if hasattr(response, 'headers'):
                # Convert headers to dict, limit size
                headers = dict(response.headers)
                details['headers'] = {k: v[:200] if isinstance(v, str) else v 
                                    for k, v in headers.items()}
            if hasattr(response, 'url'):
                details['url'] = str(response.url)
            if hasattr(response, 'request'):
                if hasattr(response.request, 'method'):
                    details['method'] = response.request.method
                if hasattr(response.request, 'url'):
                    details['request_url'] = str(response.request.url)
            
            # Get response content (limited size)
            if hasattr(response, 'text'):
                content = response.text[:1000]  # Limit to first 1KB
                details['response_body'] = content
            elif hasattr(response, 'content'):
                content = str(response.content)[:1000]
                details['response_body'] = content
                
        except Exception as e:
            details['extraction_error'] = f"Failed to extract HTTP details: {e}"
        
        return details
    
    def _write_log(self, error_context: ErrorContext) -> None:
        """Write error context to JSON Lines file."""
        try:
            with open(self.log_file, 'a') as f:
                json_line = json.dumps(asdict(error_context), default=str, ensure_ascii=False)
                f.write(json_line + '\n')
        except Exception as e:
            logger.error(f"Failed to write error log: {e}")
    
    def get_recent_errors(self, limit: int = 10) -> list:
        """Get recent errors from log file."""
        errors = []
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            errors.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Failed to read error log: {e}")
        
        return errors

def create_error_logger(component: str, log_dir: str = "logs/errors") -> GenericErrorLogger:
    """Factory function to create error logger."""
    return GenericErrorLogger(component, log_dir)