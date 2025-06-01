#!/usr/bin/env python3
"""
Script to clean Python cache files and build artifacts.
Removes __pycache__ directories, .pyc files, build directories, and other common Python artifacts.
"""

import shutil
from pathlib import Path
import argparse


def remove_directory(path: Path, description: str) -> bool:
    """Remove a directory and return True if successful."""
    try:
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            print(f"✓ Removed {description}: {path}")
            return True
        return False
    except Exception as e:
        print(f"✗ Failed to remove {description} {path}: {e}")
        return False


def remove_file(path: Path, description: str) -> bool:
    """Remove a file and return True if successful."""
    try:
        if path.exists() and path.is_file():
            path.unlink()
            print(f"✓ Removed {description}: {path}")
            return True
        return False
    except Exception as e:
        print(f"✗ Failed to remove {description} {path}: {e}")
        return False


def find_and_remove_pycache(root_dir: Path) -> int:
    """Find and remove all __pycache__ directories."""
    count = 0
    for pycache_dir in root_dir.rglob("__pycache__"):
        if remove_directory(pycache_dir, "__pycache__ directory"):
            count += 1
    return count


def find_and_remove_pyc_files(root_dir: Path) -> int:
    """Find and remove all .pyc files."""
    count = 0
    for pyc_file in root_dir.rglob("*.pyc"):
        if remove_file(pyc_file, ".pyc file"):
            count += 1
    return count


def find_and_remove_pyo_files(root_dir: Path) -> int:
    """Find and remove all .pyo files."""
    count = 0
    for pyo_file in root_dir.rglob("*.pyo"):
        if remove_file(pyo_file, ".pyo file"):
            count += 1
    return count


def clean_build_artifacts(root_dir: Path) -> int:
    """Clean build-related directories and files."""
    count = 0
    
    # Common build directories
    build_dirs = ["build", "dist", ".eggs"]
    for dir_name in build_dirs:
        build_path = root_dir / dir_name
        if remove_directory(build_path, f"{dir_name} directory"):
            count += 1
    
    # .egg-info directories
    for egg_info in root_dir.rglob("*.egg-info"):
        if remove_directory(egg_info, ".egg-info directory"):
            count += 1
    
    return count


def clean_test_artifacts(root_dir: Path) -> int:
    """Clean test-related cache and artifacts."""
    count = 0
    
    # pytest cache
    pytest_cache = root_dir / ".pytest_cache"
    if remove_directory(pytest_cache, ".pytest_cache directory"):
        count += 1
    
    # Coverage files
    coverage_files = [".coverage", ".coverage.*"]
    for pattern in coverage_files:
        for coverage_file in root_dir.glob(pattern):
            if remove_file(coverage_file, "coverage file"):
                count += 1
    
    # htmlcov directory
    htmlcov = root_dir / "htmlcov"
    if remove_directory(htmlcov, "htmlcov directory"):
        count += 1
    
    return count


def clean_mypy_cache(root_dir: Path) -> int:
    """Clean mypy cache."""
    count = 0
    mypy_cache = root_dir / ".mypy_cache"
    if remove_directory(mypy_cache, ".mypy_cache directory"):
        count += 1
    return count


def clean_jupyter_checkpoints(root_dir: Path) -> int:
    """Clean Jupyter notebook checkpoints."""
    count = 0
    for checkpoint_dir in root_dir.rglob(".ipynb_checkpoints"):
        if remove_directory(checkpoint_dir, ".ipynb_checkpoints directory"):
            count += 1
    return count


def clean_tox_cache(root_dir: Path) -> int:
    """Clean tox cache."""
    count = 0
    tox_dir = root_dir / ".tox"
    if remove_directory(tox_dir, ".tox directory"):
        count += 1
    return count


def clean_cache_directories(root_dir: Path) -> int:
    """Clean various cache directories."""
    count = 0
    
    cache_dirs = [
        ".cache",
        ".pytest_cache", 
        "__pycache__",
        ".ruff_cache",
        ".black_cache"
    ]
    
    for cache_dir in cache_dirs:
        cache_path = root_dir / cache_dir
        if remove_directory(cache_path, f"{cache_dir} directory"):
            count += 1
    
    return count


def main():
    parser = argparse.ArgumentParser(description="Clean Python cache files and build artifacts")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Path to clean (default: current directory)"
    )
    
    args = parser.parse_args()
    
    root_dir = Path(args.path).resolve()
    
    if not root_dir.exists():
        print(f"Error: Path {root_dir} does not exist")
        return 1
    
    print(f"Cleaning Python cache and build files in: {root_dir}")
    print("=" * 60)
    
    if args.dry_run:
        print("DRY RUN MODE - No files will be deleted")
        print("=" * 60)
        # For dry run, we'd need to modify the functions to just list files
        # For now, just exit with a message
        print("Dry run mode not implemented yet. Remove --dry-run to actually clean files.")
        return 0
    
    total_removed = 0
    
    # Clean different types of cache and build files
    print("\n🧹 Cleaning __pycache__ directories...")
    total_removed += find_and_remove_pycache(root_dir)
    
    print("\n🧹 Cleaning .pyc files...")
    total_removed += find_and_remove_pyc_files(root_dir)
    
    print("\n🧹 Cleaning .pyo files...")
    total_removed += find_and_remove_pyo_files(root_dir)
    
    print("\n🧹 Cleaning build artifacts...")
    total_removed += clean_build_artifacts(root_dir)
    
    print("\n🧹 Cleaning test artifacts...")
    total_removed += clean_test_artifacts(root_dir)
    
    print("\n🧹 Cleaning mypy cache...")
    total_removed += clean_mypy_cache(root_dir)
    
    print("\n🧹 Cleaning Jupyter checkpoints...")
    total_removed += clean_jupyter_checkpoints(root_dir)
    
    print("\n🧹 Cleaning tox cache...")
    total_removed += clean_tox_cache(root_dir)
    
    print("\n🧹 Cleaning other cache directories...")
    total_removed += clean_cache_directories(root_dir)
    
    print("\n" + "=" * 60)
    print(f"✨ Cleanup complete! Removed {total_removed} items.")
    
    if total_removed == 0:
        print("No cache files or build artifacts found to clean.")
    
    return 0


if __name__ == "__main__":
    exit(main())
