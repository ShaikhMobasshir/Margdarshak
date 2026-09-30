"""Quick test script for the backend API."""
import urllib.request
import json

BASE = "http://127.0.0.1:8000"

# Test health
print("=== Health Check ===")
r = urllib.request.urlopen(f"{BASE}/api/health")
print(json.loads(r.read()))

# Test recommend
print("\n=== Recommend API Test ===")
import urllib.parse
url = f"{BASE}/api/recommend?cargo_qty=30000&origin={urllib.parse.quote('Nacala (Mozambique)')}&destination=Dhamra&horizon_days=90"
r = urllib.request.urlopen(url)
data = json.loads(r.read())

print(f"Forecast points: {len(data['forecast'])}")
print(f"First 3 forecast: {data['forecast'][:3]}")

print("\nVessel recommendations:")
for v in data["vessel_recommendations"]:
    status = "FEASIBLE" if v["feasible"] else "INFEASIBLE"
    cost = f"${v['total_cost']:,.0f}" if v["total_cost"] else "N/A"
    print(f"  {v['vessel_class']:12s} [{status}] Cost: {cost}")
    if v["reasons"]:
        for reason in v["reasons"]:
            print(f"    - {reason}")

print(f"\nRisk flags: {len(data['risk_flags'])}")
if data["risk_flags"]:
    print(f"  Sample: {data['risk_flags'][0]['message'][:80]}...")

print(f"\nIdle time flags: {len(data['idle_time_flags'])}")
for f in data["idle_time_flags"]:
    print(f"  [{f['type']}] {f['message'][:80]}...")

print(f"\nMetadata: {json.dumps(data['metadata'], indent=2)}")
