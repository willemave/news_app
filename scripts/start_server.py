#!/usr/bin/env python3
"""
Startup script that runs Alembic migrations before starting the FastAPI server.
This ensures the database schema is up-to-date on every deployment.
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(command: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print('=' * 60)
    
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {description} failed!")
        print(f"Exit code: {e.returncode}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error running {description}")
        print(f"Error: {str(e)}")
        return False

def main():
    """Main function to run migrations and start the server."""
    # Change to project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    print(f"Working directory: {os.getcwd()}")
    
    # Activate virtual environment
    venv_python = str(project_root / ".venv" / "bin" / "python")
    if not Path(venv_python).exists():
        print("ERROR: Virtual environment not found. Please run 'uv venv' first.")
        sys.exit(1)
    
    # Check if alembic.ini exists
    if not Path("alembic.ini").exists():
        print("ERROR: alembic.ini not found. Please initialize Alembic first.")
        sys.exit(1)
    
    # Run migrations
    print("\n🔄 Running database migrations...")
    if not run_command([venv_python, "-m", "alembic", "upgrade", "head"], "Alembic migrations"):
        print("\n❌ Migration failed! Server will not start.")
        sys.exit(1)
    
    print("\n✅ Migrations completed successfully!")
    
    # Start the FastAPI server
    print("\n🚀 Starting FastAPI server...")
    server_command = [venv_python, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    
    # Add reload flag if in development
    if os.getenv("ENVIRONMENT", "development") == "development":
        server_command.append("--reload")
        print("Running in development mode with auto-reload enabled")
    
    # Run the server (this will block until the server is stopped)
    try:
        subprocess.run(server_command, check=True)
    except KeyboardInterrupt:
        print("\n\n✋ Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()