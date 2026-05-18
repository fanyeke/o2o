"""Create database and user if not exists.

This script creates the database and user required for the application.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("psycopg2 not installed, please run: pip install psycopg2-binary")
    sys.exit(1)

# Database connection parameters (connect to default postgres database)
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"  # Default superuser
DB_PASSWORD = None  # May need password, will try without first

# Target database and user
TARGET_DB = "coupon_agent"
TARGET_USER = "coupon_user"
TARGET_PASSWORD = "coupon_pass"


def create_database_and_user():
    """Create target database and user if they don't exist."""

    # Try multiple connection methods
    connection_methods = [
        # Method 1: peer authentication (no password, using system user)
        {
            "host": None,  # Local connection
            "user": "postgres",
            "password": None,
            "database": "postgres"
        },
        # Method 2: TCP with no password (might work for trust auth)
        {
            "host": "localhost",
            "port": DB_PORT,
            "user": "postgres",
            "password": None,
            "database": "postgres"
        },
        # Method 3: Try with common default password
        {
            "host": "localhost",
            "port": DB_PORT,
            "user": "postgres",
            "password": "postgres",
            "database": "postgres"
        },
    ]

    conn = None
    successful_method = None

    for i, method in enumerate(connection_methods, 1):
        try:
            print(f"Trying connection method {i}...")
            conn_params = {
                "user": method["user"],
                "database": method["database"]
            }
            if method.get("host"):
                conn_params["host"] = method["host"]
            if method.get("port"):
                conn_params["port"] = method["port"]
            if method.get("password"):
                conn_params["password"] = method["password"]

            conn = psycopg2.connect(**conn_params)
            successful_method = method
            print(f"✓ Connected using method {i}")
            break
        except psycopg2.OperationalError as e:
            print(f"  Method {i} failed: {e}")
            continue

    if not conn:
        print("\n✗ All connection methods failed")
        print("\nManual setup required. Please run:")
        print("  sudo -u postgres psql -c \"CREATE USER coupon_user WITH PASSWORD 'coupon_pass';\"")
        print("  sudo -u postgres psql -c \"CREATE DATABASE coupon_agent OWNER coupon_user;\"")
        print("  sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE coupon_agent TO coupon_user;\"")
        return False

    try:
        conn.autocommit = True  # Required for CREATE DATABASE
        cursor = conn.cursor()

        print(f"\nConnected to PostgreSQL successfully")

        # Check if target user exists
        cursor.execute(
            sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = {}").format(
                sql.Literal(TARGET_USER)
            )
        )
        user_exists = cursor.fetchone() is not None

        if not user_exists:
            print(f"Creating user '{TARGET_USER}'...")
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD {}").format(
                    sql.Identifier(TARGET_USER),
                    sql.Literal(TARGET_PASSWORD)
                )
            )
            print(f"✓ User '{TARGET_USER}' created")
        else:
            print(f"✓ User '{TARGET_USER}' already exists")

        # Check if target database exists
        cursor.execute(
            sql.SQL("SELECT 1 FROM pg_database WHERE datname = {}").format(
                sql.Literal(TARGET_DB)
            )
        )
        db_exists = cursor.fetchone() is not None

        if not db_exists:
            print(f"Creating database '{TARGET_DB}'...")
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(TARGET_DB),
                    sql.Identifier(TARGET_USER)
                )
            )
            print(f"✓ Database '{TARGET_DB}' created")
        else:
            print(f"✓ Database '{TARGET_DB}' already exists")

        # Grant privileges
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(TARGET_DB),
                sql.Identifier(TARGET_USER)
            )
        )
        print(f"✓ Privileges granted to '{TARGET_USER}' on '{TARGET_DB}'")

        cursor.close()
        conn.close()

        print("\n✓ Database setup completed successfully")
        print(f"Connection string: postgresql://{TARGET_USER}:{TARGET_PASSWORD}@{DB_HOST}:{DB_PORT}/{TARGET_DB}")

        return True

    except psycopg2.OperationalError as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nPossible solutions:")
        print("1. PostgreSQL might require password for postgres user")
        print("2. PostgreSQL might not allow local connections")
        print("3. PostgreSQL might be running on different port")
        print("\nTry: sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'yourpassword';\"")
        return False


if __name__ == "__main__":
    success = create_database_and_user()
    sys.exit(0 if success else 1)