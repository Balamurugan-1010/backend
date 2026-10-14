import os
import json
import sys

# Ensure backend package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models.entities import College

def import_colleges():
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "tamil_nadu_colleges.json")
    if not os.path.exists(json_path):
        print(f"Error: Dataset file not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        colleges_data = json.load(f)

    db = SessionLocal()
    try:
        existing_colleges = {c.name.strip().lower(): c for c in db.query(College).all()}
        initial_count = len(existing_colleges)
        added_count = 0

        for item in colleges_data:
            name = item["name"].strip()
            location = item.get("location", "Tamil Nadu, India").strip()
            key = name.lower()

            if key not in existing_colleges:
                new_col = College(name=name, location=location)
                db.add(new_col)
                existing_colleges[key] = new_col
                added_count += 1

        db.commit()
        final_count = db.query(College).count()

        print("=" * 60)
        print("TAMIL NADU COLLEGES DATASET IMPORT REPORT")
        print("=" * 60)
        print(f"Dataset Source: Tamil Nadu Directorate of Technical Education (DOTE)")
        print(f"                & Anna University Affiliated Institutions Directory")
        print(f"Initial colleges in database: {initial_count}")
        print(f"Newly imported colleges:     {added_count}")
        print(f"Total colleges in database:   {final_count}")
        print("=" * 60)
    finally:
        db.close()

if __name__ == "__main__":
    import_colleges()
