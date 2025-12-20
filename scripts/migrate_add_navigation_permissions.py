#!/usr/bin/env python3
"""
Migration script to add navigation permission columns to users table.
Run this after updating the auth.py User model.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add parent directory to path to import auth module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://media_user:media_password@localhost:5432/media_db")

def migrate():
    """Add navigation permission columns to users table"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        print("Starting migration: Adding navigation permission columns...")

        # Check if columns already exist
        check_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'can_view_videos'
        """)
        result = conn.execute(check_query).fetchone()

        if result:
            print("Columns already exist. Migration not needed.")
            return

        # Add the new columns with default values
        migrations = [
            "ALTER TABLE users ADD COLUMN can_view_videos BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN can_view_images BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN can_view_documents BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN can_view_categories BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN can_view_users BOOLEAN DEFAULT FALSE"
        ]

        for migration_sql in migrations:
            print(f"Executing: {migration_sql}")
            conn.execute(text(migration_sql))
            conn.commit()

        # Update admin users to have all navigation permissions
        print("Updating admin users to have all navigation permissions...")
        update_admin_sql = text("""
            UPDATE users
            SET can_view_videos = TRUE,
                can_view_images = TRUE,
                can_view_documents = TRUE,
                can_view_categories = TRUE,
                can_view_users = TRUE
            WHERE is_admin = TRUE
        """)
        conn.execute(update_admin_sql)
        conn.commit()

        print("Migration completed successfully!")
        print("\nSummary:")
        print("- Added can_view_videos column (default: TRUE)")
        print("- Added can_view_images column (default: TRUE)")
        print("- Added can_view_documents column (default: TRUE)")
        print("- Added can_view_categories column (default: FALSE)")
        print("- Added can_view_users column (default: FALSE)")
        print("- Updated all admin users to have full navigation access")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        sys.exit(1)
