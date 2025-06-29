#!/usr/bin/env python3
"""
Script to analyze recent error logs and generate an LLM prompt for fixing errors.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any
import argparse


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
    cutoff_time = datetime.now() - timedelta(hours=hours)
    all_errors = []
    
    # Process error directory
    errors_dir = logs_dir / 'errors'
    if errors_dir.exists():
        for file_path in errors_dir.glob('*.jsonl'):
            errors = parse_jsonl_file(file_path)
            for error in errors:
                try:
                    error_time = datetime.fromisoformat(error.get('timestamp', '').replace('Z', '+00:00'))
                    if error_time > cutoff_time:
                        error['source_file'] = str(file_path)
                        all_errors.append(error)
                except:
                    # Include if we can't parse timestamp
                    error['source_file'] = str(file_path)
                    all_errors.append(error)
    
    # Process main log files
    for file_path in logs_dir.glob('*.log'):
        errors = parse_log_file(file_path)
        for error in errors:
            try:
                error_time = datetime.fromisoformat(error.get('timestamp', '').replace('Z', '+00:00'))
                if error_time > cutoff_time:
                    error['source_file'] = str(file_path)
                    all_errors.append(error)
            except:
                # Include if we can't parse timestamp
                error['source_file'] = str(file_path)
                all_errors.append(error)
    
    return all_errors


def group_errors(errors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group errors by type and component."""
    grouped = defaultdict(list)
    
    for error in errors:
        # Create a key based on error type and component
        error_type = error.get('error_type', 'unknown')
        component = error.get('component', 'unknown')
        error_msg = error.get('error_message', '')
        
        # Try to extract the main error from the message
        if 'BrowserType.launch' in error_msg:
            key = 'playwright_browser_not_installed'
        elif 'json' in error_type.lower() or 'json' in error_msg.lower():
            key = 'json_parsing_errors'
        elif 'validation error' in error_msg:
            key = 'pydantic_validation_errors'
        elif 'API error' in error_msg:
            key = 'api_errors'
        else:
            key = f"{component}_{error_type}"
        
        grouped[key].append(error)
    
    return dict(grouped)


def extract_file_references(errors: List[Dict[str, Any]]) -> List[str]:
    """Extract unique file references from stack traces."""
    files = set()
    
    for error in errors:
        stack_trace = error.get('stack_trace', '')
        for line in stack_trace.split('\n'):
            if 'File "' in line and '/app/' in line:
                try:
                    file_path = line.split('File "')[1].split('"')[0]
                    if '/app/' in file_path:
                        # Extract relative path from /app/
                        relative_path = 'app/' + file_path.split('/app/')[1]
                        files.add(relative_path)
                except:
                    continue
    
    return sorted(list(files))


def generate_llm_prompt(grouped_errors: Dict[str, List[Dict[str, Any]]], hours: int) -> str:
    """Generate a comprehensive prompt for an LLM to fix the errors."""
    
    prompt = f"""# Error Analysis and Fix Request

I need help fixing errors that occurred in my FastAPI news aggregation application in the last {hours} hours. Below is a summary of the errors grouped by type, followed by specific examples.

## Project Context
- FastAPI application for news aggregation
- Uses Pydantic for data validation
- Processes content from various sources (web scraping, APIs)
- Python 3.13 with uv for package management

## Error Summary

"""
    
    # Add summary of each error type
    for error_type, errors in grouped_errors.items():
        prompt += f"### {error_type.replace('_', ' ').title()} ({len(errors)} occurrences)\n\n"
        
        # Get unique error messages for this type
        unique_messages = {}
        for error in errors[:5]:  # Limit to first 5 examples
            msg = error.get('error_message', '').split('\n')[0]  # First line only
            if msg and msg not in unique_messages:
                unique_messages[msg] = error
        
        for msg, error in unique_messages.items():
            prompt += f"- {msg}\n"
            if error.get('context_data'):
                context = error['context_data']
                if 'url' in context:
                    prompt += f"  - URL: {context['url']}\n"
                if 'strategy' in context:
                    prompt += f"  - Strategy: {context['strategy']}\n"
        
        prompt += "\n"
    
    # Add specific examples
    prompt += "## Detailed Error Examples\n\n"
    
    for error_type, errors in grouped_errors.items():
        if errors:
            prompt += f"### {error_type.replace('_', ' ').title()}\n\n"
            # Show first error in detail
            error = errors[0]
            prompt += "```json\n"
            prompt += json.dumps({
                'timestamp': error.get('timestamp'),
                'component': error.get('component'),
                'error_message': error.get('error_message'),
                'context_data': error.get('context_data'),
            }, indent=2)
            prompt += "\n```\n\n"
            
            # Add stack trace if available
            if error.get('stack_trace'):
                prompt += "Stack trace (first 20 lines):\n```\n"
                stack_lines = error['stack_trace'].split('\n')[:20]
                prompt += '\n'.join(stack_lines)
                prompt += "\n```\n\n"
    
    # Extract affected files
    all_errors = [e for errors in grouped_errors.values() for e in errors]
    affected_files = extract_file_references(all_errors)
    
    if affected_files:
        prompt += "## Affected Files\n\n"
        for file in affected_files:
            prompt += f"- {file}\n"
        prompt += "\n"
    
    # Add fix request
    prompt += """## Fix Request

Please analyze these errors and provide:

1. **Root Cause Analysis**: Identify the main issues causing these errors
2. **Immediate Fixes**: Code changes to fix the errors
3. **Prevention Strategy**: How to prevent similar errors in the future
4. **Testing Plan**: What tests should be added or run to verify the fixes

For each fix, please provide:
- The file path to modify
- The specific code changes needed
- An explanation of why this fix addresses the issue

Priority order:
1. Fix any critical errors preventing the application from running
2. Fix validation errors that cause data processing failures  
3. Fix any other errors to improve reliability

Please provide practical, implementable solutions that follow the project's coding standards (FastAPI, Pydantic, type hints, etc.)."""
    
    return prompt


def main():
    parser = argparse.ArgumentParser(description='Analyze logs and generate LLM prompt for fixes')
    parser.add_argument('--hours', type=int, default=24, help='Number of hours to look back (default: 24)')
    parser.add_argument('--output', type=str, help='Output file for the prompt (default: stdout)')
    args = parser.parse_args()
    
    # Get logs directory
    logs_dir = Path(__file__).parent.parent / 'logs'
    if not logs_dir.exists():
        print("Error: logs directory not found")
        return
    
    # Get recent errors
    print(f"Analyzing logs from the last {args.hours} hours...")
    errors = get_recent_logs(logs_dir, args.hours)
    print(f"Found {len(errors)} error entries")
    
    if not errors:
        print("No errors found in the specified time period")
        return
    
    # Group errors
    grouped_errors = group_errors(errors)
    print(f"\nError types found:")
    for error_type, error_list in grouped_errors.items():
        print(f"- {error_type}: {len(error_list)} occurrences")
    
    # Generate prompt
    prompt = generate_llm_prompt(grouped_errors, args.hours)
    
    # Output prompt
    if args.output:
        with open(args.output, 'w') as f:
            f.write(prompt)
        print(f"\nPrompt written to: {args.output}")
    else:
        print("\n" + "="*80)
        print("LLM PROMPT:")
        print("="*80 + "\n")
        print(prompt)


if __name__ == "__main__":
    main()