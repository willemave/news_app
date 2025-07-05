#!/usr/bin/env python3
"""
Script to analyze recent error logs and generate an LLM prompt for fixing errors.
Enhanced to work with the latest error logging structure and provide better insights.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import argparse
import re


def parse_jsonl_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse a JSONL file and return list of error records."""
    errors = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        errors.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass
    return errors


def parse_log_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse a regular log file and return list of error records."""
    errors = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        errors.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Try to extract error info from non-JSON lines
                        if 'error' in line.lower() or 'exception' in line.lower():
                            errors.append({
                                'timestamp': datetime.now().isoformat(),
                                 'error_message': line.strip(),
                                'file': str(file_path)
                            })
    except Exception:
        pass
    return errors


def get_recent_logs(logs_dir: Path, hours: int = 24) -> List[Dict[str, Any]]:
    """Get all logs from the past N hours."""
    # Use timezone-aware datetime for better comparison
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    all_errors = []
    
    # Process error directory
    errors_dir = logs_dir / 'errors'
    if errors_dir.exists():
        for file_path in sorted(errors_dir.glob('*.jsonl'), reverse=True):
            # Skip very old files based on filename timestamp
            if '_' in file_path.stem:
                try:
                    file_timestamp = file_path.stem.split('_')[-2] + file_path.stem.split('_')[-1]
                    file_date = datetime.strptime(file_timestamp, '%Y%m%d%H%M%S')
                    file_date = file_date.replace(tzinfo=timezone.utc)
                    if file_date < cutoff_time:
                        continue  # Skip older files
                except:
                    pass  # Process file if we can't parse filename
            
            errors = parse_jsonl_file(file_path)
            for error in errors:
                try:
                    # Handle various timestamp formats
                    timestamp_str = error.get('timestamp', '')
                    if timestamp_str:
                        # Parse ISO format with optional timezone
                        if 'Z' in timestamp_str:
                            error_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        elif '+' in timestamp_str or timestamp_str.endswith('00:00'):
                            error_time = datetime.fromisoformat(timestamp_str)
                        else:
                            # Assume UTC if no timezone
                            error_time = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
                        
                        if error_time > cutoff_time:
                            error['source_file'] = file_path.name
                            all_errors.append(error)
                except Exception as e:
                    # Include if we can't parse timestamp but log might be recent
                    error['source_file'] = file_path.name
                    error['timestamp_parse_error'] = str(e)
                    all_errors.append(error)
    
    # Process main log files
    for file_path in logs_dir.glob('*.log'):
        errors = parse_log_file(file_path)
        for error in errors:
            try:
                timestamp_str = error.get('timestamp', '')
                if timestamp_str:
                    error_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if error_time.tzinfo is None:
                        error_time = error_time.replace(tzinfo=timezone.utc)
                    if error_time > cutoff_time:
                        error['source_file'] = file_path.name
                        all_errors.append(error)
            except:
                error['source_file'] = file_path.name
                all_errors.append(error)
    
    return all_errors


def group_errors(errors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group errors by type and component with enhanced categorization."""
    grouped = defaultdict(list)
    
    for error in errors:
        # Create a key based on error type and component
        error_type = error.get('error_type', 'unknown')
        component = error.get('component', 'unknown')
        error_msg = error.get('error_message', '')
        operation = error.get('operation', '')
        
        # Enhanced error categorization based on patterns
        if 'BrowserType.launch' in error_msg or 'playwright' in error_msg.lower():
            key = 'playwright_browser_errors'
        elif 'crawl4ai' in error_msg.lower():
            key = 'crawl4ai_extraction_errors'
        elif 'json' in error_type.lower() or 'json' in error_msg.lower():
            key = 'json_parsing_errors'
        elif 'validation error' in error_msg.lower() or 'ValidationError' in error_type:
            key = 'pydantic_validation_errors'
        elif 'API error' in error_msg or 'api' in operation.lower():
            key = 'api_errors'
        elif 'HTTPException' in error_type or 'status_code' in str(error.get('http_details', {})):
            key = 'http_errors'
        elif 'timeout' in error_msg.lower() or 'TimeoutError' in error_type:
            key = 'timeout_errors'
        elif 'connection' in error_msg.lower() or 'ConnectionError' in error_type:
            key = 'connection_errors'
        elif 'pdf' in component.lower() or 'pdf' in operation.lower():
            key = 'pdf_processing_errors'
        elif 'llm' in component.lower() or 'openai' in error_msg.lower() or 'google' in error_msg.lower():
            key = 'llm_service_errors'
        elif 'database' in error_msg.lower() or 'sqlalchemy' in error_type.lower():
            key = 'database_errors'
        elif 'queue' in component.lower() or 'worker' in component.lower():
            key = 'queue_worker_errors'
        else:
            # Use component and error type as fallback
            key = f"{component}_{error_type}".replace(' ', '_').lower()
        
        grouped[key].append(error)
    
    # Sort groups by number of errors (descending)
    sorted_grouped = dict(sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True))
    
    return sorted_grouped


def extract_file_references(errors: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, int]]:
    """Extract unique file references from stack traces with occurrence counts."""
    files = set()
    file_counts = defaultdict(int)
    
    for error in errors:
        stack_trace = error.get('stack_trace', '')
        for line in stack_trace.split('\n'):
            if 'File "' in line:
                try:
                    file_path = line.split('File "')[1].split('"')[0]
                    # Handle both containerized (/app/) and local paths
                    if '/app/' in file_path:
                        # Extract relative path from /app/
                        relative_path = 'app/' + file_path.split('/app/')[1]
                        files.add(relative_path)
                        file_counts[relative_path] += 1
                    elif '/news_app/' in file_path:
                        # Handle local development paths
                        relative_path = file_path.split('/news_app/')[1]
                        files.add(relative_path)
                        file_counts[relative_path] += 1
                except:
                    continue
    
    # Sort by occurrence count (most frequent first)
    sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
    return [f[0] for f in sorted_files], dict(file_counts)


def generate_llm_prompt(grouped_errors: Dict[str, List[Dict[str, Any]]], hours: int) -> str:
    """Generate a comprehensive prompt for an LLM to fix the errors."""
    
    # Calculate total errors
    total_errors = sum(len(errors) for errors in grouped_errors.values())
    
    prompt = f"""# Error Analysis and Fix Request

I need help fixing errors that occurred in my FastAPI news aggregation application in the last {hours} hours.

## Summary Statistics
- **Total Errors**: {total_errors}
- **Error Categories**: {len(grouped_errors)}
- **Time Period**: Last {hours} hours

## Project Context
- FastAPI application for news aggregation and content processing
- Uses Pydantic v2 for data validation
- Processes content from various sources (web scraping, APIs, PDFs)
- Python 3.13 with uv for package management
- Deployed on Fly.io with PostgreSQL database
- Uses Google Flash and OpenAI for LLM services
- Content extraction with crawl4ai and custom strategies

## Error Summary by Category

"""
    
    # Add summary of each error type with better formatting
    for error_type, errors in grouped_errors.items():
        prompt += f"### {error_type.replace('_', ' ').title()} ({len(errors)} occurrences)\n\n"
        
        # Group by unique error patterns
        error_patterns = defaultdict(list)
        for error in errors:
            msg = error.get('error_message', '').split('\n')[0][:200]  # First line, truncated
            error_patterns[msg].append(error)
        
        # Show top patterns
        for msg, pattern_errors in list(error_patterns.items())[:3]:
            prompt += f"- **{msg}** ({len(pattern_errors)} times)\n"
            
            # Show context from first occurrence
            first_error = pattern_errors[0]
            if first_error.get('context_data'):
                context = first_error['context_data']
                relevant_context = []
                if 'url' in context:
                    relevant_context.append(f"URL: {context['url']}")
                if 'strategy' in context:
                    relevant_context.append(f"Strategy: {context['strategy']}")
                if 'method' in context:
                    relevant_context.append(f"Method: {context['method']}")
                if 'item_id' in first_error:
                    relevant_context.append(f"Item: {first_error['item_id']}")
                
                if relevant_context:
                    prompt += f"  - Context: {', '.join(relevant_context)}\n"
        
        prompt += "\n"
    
    # Add detailed examples for top error categories
    prompt += "## Detailed Error Analysis\n\n"
    
    # Show details for top 3 error categories
    for i, (error_type, errors) in enumerate(list(grouped_errors.items())[:3]):
        prompt += f"### {i+1}. {error_type.replace('_', ' ').title()}\n\n"
        
        # Show most recent error with full details
        error = errors[0]
        prompt += "**Most Recent Occurrence:**\n```json\n"
        prompt += json.dumps({
            'timestamp': error.get('timestamp'),
            'component': error.get('component'),
            'operation': error.get('operation'),
            'error_type': error.get('error_type'),
            'error_message': error.get('error_message'),
            'context_data': error.get('context_data'),
            'item_id': error.get('item_id')
        }, indent=2, default=str)
        prompt += "\n```\n\n"
        
        # Add stack trace if available
        if error.get('stack_trace'):
            prompt += "**Stack Trace:**\n```python\n"
            stack_lines = error['stack_trace'].split('\n')[:15]
            prompt += '\n'.join(stack_lines)
            if len(error['stack_trace'].split('\n')) > 15:
                prompt += "\n... (truncated)"
            prompt += "\n```\n\n"
        
        # HTTP details if relevant
        if error.get('http_details'):
            http = error['http_details']
            prompt += "**HTTP Details:**\n"
            if 'status_code' in http:
                prompt += f"- Status Code: {http['status_code']}\n"
            if 'url' in http:
                prompt += f"- URL: {http['url']}\n"
            if 'method' in http:
                prompt += f"- Method: {http['method']}\n"
            prompt += "\n"
    
    # Extract affected files with counts
    all_errors = [e for errors in grouped_errors.values() for e in errors]
    affected_files, file_counts = extract_file_references(all_errors)
    
    if affected_files:
        prompt += "## Most Affected Files\n\n"
        for file in affected_files[:10]:  # Top 10 files
            count = file_counts.get(file, 0)
            prompt += f"- `{file}` ({count} errors)\n"
        if len(affected_files) > 10:
            prompt += f"- ... and {len(affected_files) - 10} more files\n"
        prompt += "\n"
    
    # Add patterns and insights
    prompt += "## Error Patterns Detected\n\n"
    
    # Detect common patterns
    patterns = []
    if 'crawl4ai_extraction_errors' in grouped_errors:
        patterns.append("- Crawl4ai extraction failures - may need fallback strategies")
    if 'timeout_errors' in grouped_errors:
        patterns.append("- Timeout errors - consider increasing timeouts or adding retries")
    if 'pydantic_validation_errors' in grouped_errors:
        patterns.append("- Data validation failures - input data doesn't match expected schemas")
    if 'llm_service_errors' in grouped_errors:
        patterns.append("- LLM service errors - API rate limits or service availability issues")
    if 'database_errors' in grouped_errors:
        patterns.append("- Database errors - connection or query issues")
    
    if patterns:
        prompt += '\n'.join(patterns) + '\n\n'
    
    # Add fix request with specific focus areas
    prompt += """## Fix Request

Please analyze these errors and provide:

1. **Critical Fixes** (Errors preventing normal operation):
   - Identify showstopper issues
   - Provide immediate fixes with code snippets
   - Include rollback strategy if needed

2. **Root Cause Analysis**:
   - Common patterns across error types
   - System design issues contributing to errors
   - Configuration problems

3. **Specific Code Changes**:
   - File path and line numbers
   - Before/after code snippets
   - Explanation of each change

4. **Preventive Measures**:
   - Input validation improvements
   - Better error handling patterns
   - Retry logic and circuit breakers
   - Monitoring and alerting recommendations

5. **Testing Strategy**:
   - Unit tests for fixed components
   - Integration tests for error scenarios
   - Commands to verify fixes

## Implementation Notes
- Follow project coding standards (RORO pattern, type hints, error handling)
- Use existing error handling utilities (GenericErrorLogger)
- Ensure backward compatibility
- Consider performance implications
- Add proper logging for debugging

Please prioritize fixes based on:
1. Frequency of occurrence
2. Impact on user experience
3. Ease of implementation
4. Long-term maintainability"""
    
    return prompt


def analyze_error_trends(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze error trends over time."""
    if not errors:
        return {}
    
    # Group errors by hour
    hourly_counts = defaultdict(int)
    component_counts = defaultdict(int)
    
    for error in errors:
        try:
            timestamp = error.get('timestamp', '')
            if timestamp:
                error_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hour_key = error_time.strftime('%Y-%m-%d %H:00')
                hourly_counts[hour_key] += 1
        except:
            pass
        
        component = error.get('component', 'unknown')
        component_counts[component] += 1
    
    return {
        'hourly_distribution': dict(sorted(hourly_counts.items())),
        'component_distribution': dict(sorted(component_counts.items(), key=lambda x: x[1], reverse=True))
    }


def generate_summary_report(errors: List[Dict[str, Any]], grouped_errors: Dict[str, List[Dict[str, Any]]]) -> str:
    """Generate a concise summary report."""
    trends = analyze_error_trends(errors)
    
    report = "## Quick Summary\n\n"
    report += f"- **Total Errors**: {len(errors)}\n"
    report += f"- **Error Types**: {len(grouped_errors)}\n"
    report += f"- **Top 3 Error Types**:\n"
    
    for error_type, error_list in list(grouped_errors.items())[:3]:
        percentage = (len(error_list) / len(errors)) * 100
        report += f"  - {error_type.replace('_', ' ').title()}: {len(error_list)} ({percentage:.1f}%)\n"
    
    if trends.get('component_distribution'):
        report += f"\n- **Most Affected Components**:\n"
        for component, count in list(trends['component_distribution'].items())[:5]:
            report += f"  - {component}: {count} errors\n"
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description='Analyze error logs and generate LLM prompts for fixes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze last 24 hours (default)
  python scripts/analyze_logs_for_fixes.py
  
  # Analyze last 48 hours and save to file
  python scripts/analyze_logs_for_fixes.py --hours 48 --output error_analysis.md
  
  # Quick summary only
  python scripts/analyze_logs_for_fixes.py --summary
  
  # Filter by component
  python scripts/analyze_logs_for_fixes.py --component html_strategy --hours 72
  
  # Export errors as JSON for further analysis
  python scripts/analyze_logs_for_fixes.py --json errors.json --hours 168
  
  # Show only error types with 5+ occurrences
  python scripts/analyze_logs_for_fixes.py --min-errors 5
        """
    )
    parser.add_argument('--hours', type=int, default=24, help='Number of hours to look back (default: 24)')
    parser.add_argument('--output', type=str, help='Output file for the prompt (default: stdout)')
    parser.add_argument('--summary', action='store_true', help='Show summary only without full prompt')
    parser.add_argument('--min-errors', type=int, default=1, help='Minimum errors per category to include (default: 1)')
    parser.add_argument('--json', type=str, help='Export errors as JSON to specified file')
    parser.add_argument('--component', type=str, help='Filter errors by component name')
    args = parser.parse_args()
    
    # Get logs directory
    logs_dir = Path(__file__).parent.parent / 'logs'
    if not logs_dir.exists():
        print("Error: logs directory not found")
        return
    
    # Get recent errors
    print(f"Analyzing logs from the last {args.hours} hours...")
    errors = get_recent_logs(logs_dir, args.hours)
    
    # Filter by component if specified
    if args.component:
        errors = [e for e in errors if e.get('component', '').lower() == args.component.lower()]
        print(f"Filtered to component '{args.component}': {len(errors)} errors")
    else:
        print(f"Found {len(errors)} error entries")
    
    if not errors:
        print("No errors found in the specified time period")
        return
    
    # Export as JSON if requested
    if args.json:
        with open(args.json, 'w') as f:
            json.dump({
                'metadata': {
                    'hours': args.hours,
                    'component': args.component,
                    'total_errors': len(errors),
                    'export_time': datetime.now().isoformat()
                },
                'errors': errors
            }, f, indent=2, default=str)
        print(f"Exported {len(errors)} errors to {args.json}")
        if args.summary:
            return
    
    # Group errors
    grouped_errors = group_errors(errors)
    
    # Filter by minimum error count if specified
    if args.min_errors > 1:
        grouped_errors = {k: v for k, v in grouped_errors.items() if len(v) >= args.min_errors}
        print(f"Filtered to {len(grouped_errors)} error types with at least {args.min_errors} occurrences")
    
    # Generate summary
    summary = generate_summary_report(errors, grouped_errors)
    print("\n" + summary)
    
    if args.summary:
        return
    
    print(f"\nDetailed error breakdown:")
    for error_type, error_list in grouped_errors.items():
        print(f"- {error_type}: {len(error_list)} occurrences")
    
    # Generate prompt
    prompt = generate_llm_prompt(grouped_errors, args.hours)
    
    # Output prompt
    if args.output:
        with open(args.output, 'w') as f:
            f.write(prompt)
        print(f"\nPrompt written to: {args.output}")
        print(f"You can now paste this into an LLM to get fix recommendations.")
    else:
        print("\n" + "="*80)
        print("LLM PROMPT:")
        print("="*80 + "\n")
        print(prompt)


if __name__ == "__main__":
    main()