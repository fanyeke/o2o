#!/usr/bin/env python3
"""Import CSV data files into raw database tables."""

import argparse
import pandas as pd
from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.domain.raw.offline_train import OfflineTrain
from app.domain.raw.offline_test import OfflineTest


def import_offline_train(csv_path: str = "/app/data/offline_train.csv") -> int:
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    df.columns = [c.lower() for c in df.columns]

    records = df.to_dict(orient="records")
    print(f"Inserting {len(records)} rows into raw.offline_train...")

    with SessionLocal() as session:
        session.execute(text("TRUNCATE TABLE raw.offline_train"))
        session.commit()
        session.bulk_insert_mappings(OfflineTrain, records)
        session.commit()

    print(f"Done. Imported {len(records)} rows.")
    return len(records)


def import_offline_test(csv_path: str = "/app/data/offline_test.csv") -> int:
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    df.columns = [c.lower() for c in df.columns]

    records = df.to_dict(orient="records")

    with SessionLocal() as session:
        session.execute(text("TRUNCATE TABLE raw.offline_test"))
        session.commit()
        session.bulk_insert_mappings(OfflineTest, records)
        session.commit()

    print(f"Done. Imported {len(records)} rows.")
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import datasets into raw layer")
    parser.add_argument("--train", default="/app/data/offline_train.csv")
    parser.add_argument("--test", default="/app/data/offline_test.csv")
    args = parser.parse_args()

    train_rows = import_offline_train(args.train)
    test_rows = import_offline_test(args.test)
    print(f"\nSummary: {train_rows + test_rows} total rows imported.")
