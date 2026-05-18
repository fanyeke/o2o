#!/usr/bin/env python3
"""Create database schemas for o2o project."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine, SessionLocal

def create_schemas():
    """Create required schemas."""
    db = SessionLocal()

    try:
        # Create schemas
        schemas = ['raw', 'staging', 'feature', 'application']

        for schema in schemas:
            db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            print(f"✓ Schema '{schema}' created")

        db.commit()

        # Verify
        result = db.execute(text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN ('raw', 'staging', 'feature', 'application')
        """)).fetchall()

        print(f"\n✓ Created {len(result)} schemas: {[r[0] for r in result]}")

    except Exception as e:
        db.rollback()
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_schemas()