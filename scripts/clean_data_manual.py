#!/usr/bin/env python3
"""Manually run data cleaning service."""

import time
from app.core.database import SessionLocal
from app.services.data_cleaning_service import DataCleaningService


def main():
    """Run data cleaning service."""
    print("Starting data cleaning...")
    start_time = time.time()

    with SessionLocal() as session:
        service = DataCleaningService(session)
        result = service.clean_all_data(batch_size=10000)

    end_time = time.time()
    duration = end_time - start_time

    print(f"\nData cleaning completed in {duration:.2f} seconds")
    print(f"Receipt events: {result['receipt_events']}")
    print(f"Consumption events: {result['consumption_events']}")
    print(f"Processing rate: {(result['receipt_events'] + result['consumption_events']) / duration:.0f} records/sec")


if __name__ == "__main__":
    main()