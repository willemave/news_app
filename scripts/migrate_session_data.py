#!/usr/bin/env python3
"""
Migrate favorites and read status from old session_id schema to new user_id schema.

This script helps recover data after the migration from session_id to user_id based tracking.
It migrates ALL data from the backup database to the specified user_id.

Usage:
    # List available users
    python scripts/migrate_session_data.py --list-users

    # Migrate all data from backup to a user_id (dry run first)
    python scripts/migrate_session_data.py --backup-db backup.db --user-id 1 --dry-run

    # Migrate all data from backup to a user_id
    python scripts/migrate_session_data.py --backup-db backup.db --user-id 1
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, create_engine, select, text
from sqlalchemy.orm import Session, declarative_base

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import get_db
from app.models.schema import ContentFavorites, ContentReadStatus, ContentUnlikes
from app.models.user import User

# Define old schema models for backup database
BackupBase = declarative_base()


class OldContentFavorites(BackupBase):
    """Old schema with session_id."""

    __tablename__ = "content_favorites"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False)
    content_id = Column(Integer, nullable=False)
    favorited_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)


class OldContentReadStatus(BackupBase):
    """Old schema with session_id."""

    __tablename__ = "content_read_status"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False)
    content_id = Column(Integer, nullable=False)
    read_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)


class OldContentUnlikes(BackupBase):
    """Old schema with session_id."""

    __tablename__ = "content_unlikes"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False)
    content_id = Column(Integer, nullable=False)
    unliked_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)


def list_users(db: Session) -> list[User]:
    """List all users in the database."""
    users = db.execute(select(User)).scalars().all()
    return list(users)


def get_backup_stats(backup_db_path: str) -> dict[str, int]:
    """Get counts of data in backup database."""
    backup_engine = create_engine(f"sqlite:///{backup_db_path}")
    with Session(backup_engine) as backup_db:
        # Count records in each table
        fav_count = backup_db.execute(text("SELECT COUNT(*) FROM content_favorites")).scalar()
        read_count = backup_db.execute(text("SELECT COUNT(*) FROM content_read_status")).scalar()
        unlike_count = backup_db.execute(text("SELECT COUNT(*) FROM content_unlikes")).scalar()

    return {
        "favorites": fav_count,
        "read_status": read_count,
        "unlikes": unlike_count,
    }


def migrate_data(
    backup_db_path: str,
    user_id: int,
    db: Session,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Migrate ALL favorites and read status from backup database to new schema.

    Args:
        backup_db_path: Path to backup database file
        user_id: User ID to migrate to
        db: Current database session
        dry_run: If True, only report what would be migrated without making changes

    Returns:
        Dictionary with counts of migrated records
    """
    # Connect to backup database
    backup_engine = create_engine(f"sqlite:///{backup_db_path}")

    stats = {
        "favorites_found": 0,
        "favorites_migrated": 0,
        "favorites_skipped": 0,
        "read_status_found": 0,
        "read_status_migrated": 0,
        "read_status_skipped": 0,
        "unlikes_found": 0,
        "unlikes_migrated": 0,
        "unlikes_skipped": 0,
    }

    with Session(backup_engine) as backup_db:
        # Migrate ALL favorites (regardless of session_id)
        print("\n🔍 Loading all favorites from backup...")
        old_favorites = backup_db.execute(select(OldContentFavorites)).scalars().all()

        stats["favorites_found"] = len(old_favorites)
        print(f"   Found {stats['favorites_found']} favorite records")

        if not dry_run:
            for old_fav in old_favorites:
                # Check if already exists
                existing = db.execute(
                    select(ContentFavorites).where(
                        ContentFavorites.user_id == user_id,
                        ContentFavorites.content_id == old_fav.content_id,
                    )
                ).scalar_one_or_none()

                if existing:
                    stats["favorites_skipped"] += 1
                    continue

                # Create new record
                new_fav = ContentFavorites(
                    user_id=user_id,
                    content_id=old_fav.content_id,
                    favorited_at=old_fav.favorited_at,
                    created_at=old_fav.created_at,
                )
                db.add(new_fav)
                stats["favorites_migrated"] += 1

        # Migrate ALL read status (regardless of session_id)
        print("\n🔍 Loading all read status from backup...")
        old_read_status = backup_db.execute(select(OldContentReadStatus)).scalars().all()

        stats["read_status_found"] = len(old_read_status)
        print(f"   Found {stats['read_status_found']} read status records")

        if not dry_run:
            for old_read in old_read_status:
                # Check if already exists
                existing = db.execute(
                    select(ContentReadStatus).where(
                        ContentReadStatus.user_id == user_id,
                        ContentReadStatus.content_id == old_read.content_id,
                    )
                ).scalar_one_or_none()

                if existing:
                    stats["read_status_skipped"] += 1
                    continue

                # Create new record
                new_read = ContentReadStatus(
                    user_id=user_id,
                    content_id=old_read.content_id,
                    read_at=old_read.read_at,
                    created_at=old_read.created_at,
                )
                db.add(new_read)
                stats["read_status_migrated"] += 1

        # Migrate ALL unlikes (regardless of session_id)
        print("\n🔍 Loading all unlikes from backup...")
        old_unlikes = backup_db.execute(select(OldContentUnlikes)).scalars().all()

        stats["unlikes_found"] = len(old_unlikes)
        print(f"   Found {stats['unlikes_found']} unlike records")

        if not dry_run:
            for old_unlike in old_unlikes:
                # Check if already exists
                existing = db.execute(
                    select(ContentUnlikes).where(
                        ContentUnlikes.user_id == user_id,
                        ContentUnlikes.content_id == old_unlike.content_id,
                    )
                ).scalar_one_or_none()

                if existing:
                    stats["unlikes_skipped"] += 1
                    continue

                # Create new record
                new_unlike = ContentUnlikes(
                    user_id=user_id,
                    content_id=old_unlike.content_id,
                    unliked_at=old_unlike.unliked_at,
                    created_at=old_unlike.created_at,
                )
                db.add(new_unlike)
                stats["unlikes_migrated"] += 1

        if not dry_run:
            db.commit()
            print("\n✅ Migration committed to database")
        else:
            print("\n⚠️  Dry run - no changes made")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate ALL favorites and read status from backup to user-based tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available users
  python scripts/migrate_session_data.py --list-users

  # Show stats from backup database
  python scripts/migrate_session_data.py --backup-db backup.db --show-stats

  # Migrate all data (dry run first)
  python scripts/migrate_session_data.py --backup-db backup.db --user-id 1 --dry-run

  # Migrate all data for real
  python scripts/migrate_session_data.py --backup-db backup.db --user-id 1
        """,
    )
    parser.add_argument(
        "--list-users", action="store_true", help="List all users in current database"
    )
    parser.add_argument(
        "--show-stats", action="store_true", help="Show record counts in backup database"
    )
    parser.add_argument("--backup-db", help="Path to backup database file (SQLite)")
    parser.add_argument("--user-id", type=int, help="User ID to migrate to")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be migrated without making changes"
    )

    args = parser.parse_args()

    # List users
    if args.list_users:
        print("\n📋 Available users:\n")
        with get_db() as db:
            users = list_users(db)
            if not users:
                print("   No users found in database")
                return

            for user in users:
                admin_badge = "👑 ADMIN" if user.is_admin else ""
                active_badge = "✅ ACTIVE" if user.is_active else "❌ INACTIVE"
                print(
                    f"   ID: {user.id:3d} | {user.email:40s} | {user.full_name or '(no name)':30s} | {admin_badge:8s} | {active_badge}"
                )
        return

    # Show stats from backup
    if args.show_stats:
        if not args.backup_db:
            print("❌ Error: --backup-db is required with --show-stats")
            sys.exit(1)

        if not Path(args.backup_db).exists():
            print(f"❌ Error: Backup database not found: {args.backup_db}")
            sys.exit(1)

        print(f"\n📊 Backup database stats: '{args.backup_db}'\n")
        stats = get_backup_stats(args.backup_db)

        print(f"   Favorites:    {stats['favorites']:6d} records")
        print(f"   Read Status:  {stats['read_status']:6d} records")
        print(f"   Unlikes:      {stats['unlikes']:6d} records")
        print(f"   {'─' * 30}")
        print(f"   Total:        {sum(stats.values()):6d} records")
        return

    # Validate migration arguments
    if not args.backup_db:
        print("❌ Error: --backup-db is required for migration")
        print("   Use --list-users or --show-stats for other operations")
        sys.exit(1)

    if args.user_id is None:
        print("❌ Error: --user-id is required")
        sys.exit(1)

    if not Path(args.backup_db).exists():
        print(f"❌ Error: Backup database not found: {args.backup_db}")
        sys.exit(1)

    # Run migration
    print("\n" + "=" * 80)
    print("🔄 MIGRATION CONFIGURATION")
    print("=" * 80)
    print(f"Backup database:  {args.backup_db}")
    print(f"Target user ID:   {args.user_id}")
    print(
        f"Mode:             {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will modify database)'}"
    )
    print("Strategy:         Migrate ALL data from backup (all sessions)")
    print("=" * 80)

    with get_db() as db:
        # Verify user exists
        user = db.execute(select(User).where(User.id == args.user_id)).scalar_one_or_none()
        if not user:
            print(f"\n❌ Error: User ID {args.user_id} not found in database")
            print("   Use --list-users to see available users")
            sys.exit(1)

        print(f"\n✅ Target user verified: {user.email} ({user.full_name or 'no name'})")

        # Run migration
        stats = migrate_data(
            backup_db_path=args.backup_db,
            user_id=args.user_id,
            db=db,
            dry_run=args.dry_run,
        )

        # Print summary
        print("\n" + "=" * 80)
        print("📊 MIGRATION SUMMARY")
        print("=" * 80)
        print(
            f"Favorites:    {stats['favorites_found']:4d} found | {stats['favorites_migrated']:4d} migrated | {stats['favorites_skipped']:4d} skipped"
        )
        print(
            f"Read Status:  {stats['read_status_found']:4d} found | {stats['read_status_migrated']:4d} migrated | {stats['read_status_skipped']:4d} skipped"
        )
        print(
            f"Unlikes:      {stats['unlikes_found']:4d} found | {stats['unlikes_migrated']:4d} migrated | {stats['unlikes_skipped']:4d} skipped"
        )
        print("=" * 80)

        total_migrated = (
            stats["favorites_migrated"] + stats["read_status_migrated"] + stats["unlikes_migrated"]
        )
        total_skipped = (
            stats["favorites_skipped"] + stats["read_status_skipped"] + stats["unlikes_skipped"]
        )

        if args.dry_run:
            print(
                f"\n💡 DRY RUN: Would migrate {total_migrated} records (skip {total_skipped} duplicates)"
            )
            print("   Run without --dry-run to apply changes")
        else:
            print(
                f"\n✅ COMPLETE: Migrated {total_migrated} records (skipped {total_skipped} duplicates)"
            )


if __name__ == "__main__":
    main()
