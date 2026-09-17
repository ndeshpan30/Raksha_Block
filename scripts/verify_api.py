"""
RAKSHA-BLOCK: Verify FastAPI GET /requests Endpoint
Invokes the FastAPI test client to query GET /requests and displays
the actual JSON response for sample records.
"""

import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import app

def main():
    print("=" * 80)
    print("  RAKSHA-BLOCK: Verifying FastAPI GET /requests Endpoint")
    print("=" * 80)

    client = TestClient(app)

    # 1. Test GET /requests (all records)
    response = client.get("/requests")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    total_count = len(data)

    print(f"\n[+] GET /requests status code: {response.status_code}")
    print(f"[+] Total records returned: {total_count}")
    assert total_count == 240, f"Expected 240 records, got {total_count}"

    # 2. Test GET /requests?department=TRD
    resp_trd = client.get("/requests?department=TRD")
    assert resp_trd.status_code == 200
    data_trd = resp_trd.json()
    print(f"[+] Filtered GET /requests?department=TRD count: {len(data_trd)}")
    assert len(data_trd) == 77

    # 3. Test GET /api/v1/requests (alias route)
    resp_v1 = client.get("/api/v1/requests?limit=5")
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    print(f"[+] Alias GET /api/v1/requests?limit=5 count: {len(data_v1)}")
    assert len(data_v1) == 5

    # 4. Print actual JSON response for first 3 records
    print("\n" + "-" * 80)
    print("  ACTUAL JSON RESPONSE FOR FIRST 3 RECORDS (GET /requests?limit=3)")
    print("-" * 80)
    sample_resp = client.get("/requests?limit=3")
    sample_data = sample_resp.json()
    print(json.dumps(sample_data, indent=2))

    print("\n" + "=" * 80)
    print("  FastAPI endpoint GET /requests verified successfully end-to-end!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
