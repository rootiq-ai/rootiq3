#!/usr/bin/env python3
"""
Database setup script for Alert Monitoring MVP
Creates database tables and initial configuration
"""

import sys
import os
import asyncio
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Import app modules
try:
    from backend.app.config.settings import settings
    from backend.app.models.alert import Base
    from backend.app.database.connection import async_engine, sync_engine
except ImportError as e:
    print(f"Error importing app modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    
    print("Checking if database exists...")
    
    # Parse database URL to get connection details
    db_url = settings.DATABASE_URL
    
    # Extract database name and connection details
    if db_url.startswith("postgresql://"):
        # Format: postgresql://user:password@host:port/database
        parts = db_url.replace("postgresql://", "").split("/")
        db_name = parts[-1]
        connection_base = parts[0]
        
        # Connect to postgres database to create our target database
        postgres_url = f"postgresql://{connection_base}/postgres"
        
        try:
            # Connect to postgres database
            conn = psycopg2.connect(postgres_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
            exists = cursor.fetchone()
            
            if not exists:
                print(f"Creating database '{db_name}'...")
                cursor.execute(f'CREATE DATABASE "{db_name}"')
                print(f"✅ Database '{db_name}' created successfully")
            else:
                print(f"✅ Database '{db_name}' already exists")
            
            cursor.close()
            conn.close()
            
        except psycopg2.Error as e:
            print(f"❌ Error creating database: {e}")
            print("Please ensure PostgreSQL is running and connection details are correct")
            sys.exit(1)
    
    else:
        print("❌ Unsupported database URL format")
        sys.exit(1)


def create_tables():
    """Create database tables"""
    
    print("Creating database tables...")
    
    try:
        # Create tables using sync engine
        Base.metadata.create_all(bind=sync_engine)
        print("✅ Database tables created successfully")
        
        # Verify tables were created
        with sync_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result]
            print(f"📋 Created tables: {', '.join(tables)}")
            
    except SQLAlchemyError as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)


def test_database_connection():
    """Test database connection"""
    
    print("Testing database connection...")
    
    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Database connection successful")
            print(f"📋 PostgreSQL version: {version}")
            
    except SQLAlchemyError as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)


async def test_async_connection():
    """Test async database connection"""
    
    print("Testing async database connection...")
    
    try:
        from backend.app.database.connection import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            await session.commit()
            
        print("✅ Async database connection successful")
        
    except Exception as e:
        print(f"❌ Async database connection failed: {e}")
        sys.exit(1)


def create_indexes():
    """Create additional indexes for performance"""
    
    print("Creating performance indexes...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_alerts_host_service ON alerts(host_name, service_name);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_group_id ON alerts(group_id);",
        "CREATE INDEX IF NOT EXISTS idx_groups_host_service ON alert_groups(host_name, service_name);",
        "CREATE INDEX IF NOT EXISTS idx_groups_created_at ON alert_groups(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_groups_rca_status ON alert_groups(rca_generated);"
    ]
    
    try:
        with sync_engine.connect() as conn:
            for index_sql in indexes:
                conn.execute(text(index_sql))
                conn.commit()
        
        print("✅ Performance indexes created successfully")
        
    except SQLAlchemyError as e:
        print(f"⚠️ Warning: Some indexes may not have been created: {e}")


def insert_sample_data():
    """Insert sample data for testing"""
    
    print("Would you like to insert sample data for testing? (y/N): ", end="")
    choice = input().lower()
    
    if choice in ['y', 'yes']:
        print("Inserting sample data...")
        
        sample_alerts = [
            {
                'monitoring_system': 'setup_script',
                'host_name': 'web-server-01',
                'service_name': 'nginx',
                'alert_name': 'HighCPUUsage',
                'severity': 'high',
                'message': 'CPU usage is above 90% for the last 5 minutes',
                'details': '{"cpu_percentage": 92.5, "threshold": 90}'
            },
            {
                'monitoring_system': 'setup_script',
                'host_name': 'web-server-01',
                'service_name': 'nginx',
                'alert_name': 'HighMemoryUsage',
                'severity': 'medium',
                'message': 'Memory usage is above 80%',
                'details': '{"memory_percentage": 85.2, "threshold": 80}'
            },
            {
                'monitoring_system': 'setup_script',
                'host_name': 'db-server-01',
                'service_name': 'postgresql',
                'alert_name': 'SlowQuery',
                'severity': 'medium',
                'message': 'Database query taking longer than expected',
                'details': '{"query_time": 15.3, "threshold": 10}'
            }
        ]
        
        try:
            with sync_engine.connect() as conn:
                for alert in sample_alerts:
                    conn.execute(text("""
                        INSERT INTO alerts (
                            id, monitoring_system, host_name, service_name, 
                            alert_name, severity, message, details
                        ) VALUES (
                            gen_random_uuid()::text, :monitoring_system, :host_name, 
                            :service_name, :alert_name, :severity, :message, :details
                        )
                    """), alert)
                
                conn.commit()
            
            print("✅ Sample data inserted successfully")
            
        except SQLAlchemyError as e:
            print(f"⚠️ Warning: Could not insert sample data: {e}")


def main():
    """Main setup function"""
    
    print("🚀 Alert Monitoring MVP - Database Setup")
    print("=" * 50)
    
    # Check environment
    print(f"📋 Database URL: {settings.DATABASE_URL}")
    print(f"📋 Environment: {'Development' if settings.DEBUG else 'Production'}")
    print()
    
    # Setup steps
    steps = [
        ("Creating database if needed", create_database_if_not_exists),
        ("Testing database connection", test_database_connection),
        ("Creating tables", create_tables),
        ("Testing async connection", lambda: asyncio.run(test_async_connection())),
        ("Creating performance indexes", create_indexes),
    ]
    
    for step_name, step_func in steps:
        print(f"🔄 {step_name}...")
        try:
            step_func()
        except Exception as e:
            print(f"❌ Failed: {e}")
            sys.exit(1)
        print()
    
    # Optional sample data
    insert_sample_data()
    
    print("🎉 Database setup completed successfully!")
    print()
    print("Next steps:")
    print("1. Run `python scripts/setup_chromadb.py` to setup ChromaDB")
    print("2. Start the backend: `cd backend && python -m app.main`")
    print("3. Start the frontend: `cd frontend && streamlit run streamlit_app.py`")


if __name__ == "__main__":
    main()
