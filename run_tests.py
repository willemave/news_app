#!/usr/bin/env python3
"""Run tests for the sequential processor implementation."""

import sys
import subprocess
import os

def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode == 0:
        print(f"✓ {description} passed")
    else:
        print(f"✗ {description} failed")
    
    return result.returncode

def main():
    """Run all tests."""
    print("Sequential Processor Implementation Tests")
    print("="*60)
    
    # Change to project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    tests = [
        ("pytest tests/pipeline/test_sequential_task_processor.py -v", 
         "Sequential Task Processor Tests"),
        
        ("pytest tests/pipeline/test_content_worker.py -v", 
         "Content Worker Tests"),
        
        ("pytest tests/processing_strategies/test_html_strategy_event_loop.py -v", 
         "HTML Strategy Event Loop Tests"),
        
        ("pytest tests/services/test_sync_methods.py -v", 
         "Synchronous Methods Tests"),
        
        ("pytest tests/integration/test_pipeline_integration.py -v", 
         "Pipeline Integration Tests"),
        
        ("python test_thread_processor.py", 
         "Sequential Processor Integration Test"),
    ]
    
    failed_tests = []
    
    for cmd, description in tests:
        returncode = run_command(cmd, description)
        if returncode != 0:
            failed_tests.append(description)
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print('='*60)
    
    if not failed_tests:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {len(failed_tests)} test(s) failed:")
        for test in failed_tests:
            print(f"  - {test}")
        return 1

if __name__ == "__main__":
    sys.exit(main())