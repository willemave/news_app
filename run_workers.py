#!/usr/bin/env python3
"""Run the sequential task processor."""

import asyncio
import sys
from app.pipeline.sequential_task_processor import SequentialTaskProcessor


async def main():
    """Main entry point."""
    max_tasks = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    print(f"Starting sequential task processor...")
    if max_tasks:
        print(f"Will process up to {max_tasks} tasks")
    print("Press Ctrl+C to stop")
    
    processor = SequentialTaskProcessor()
    await processor.run(max_tasks=max_tasks)


if __name__ == "__main__":
    asyncio.run(main())