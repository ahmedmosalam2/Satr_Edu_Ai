import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

from fastapi.testclient import TestClient
from main import app

def test_routes_verbose():
    with TestClient(app) as client:
        print("=" * 70)
        print("   STARTING FULL ROUTE INTEGRITY CHECK")
        print("=" * 70)

        # Step 1: Get OpenAPI schema
        response = client.get("/openapi.json")
        if response.status_code != 200:
            print(f"[FAIL] Could not generate OpenAPI schema: {response.status_code}")
            sys.exit(1)

        schema = response.json()
        paths = schema.get("paths", {})

        print(f"\n[OK] OpenAPI schema generated successfully.")
        print(f"[OK] Discovered {len(paths)} unique endpoint paths.\n")

        print("=" * 70)
        print("   ALL REGISTERED ROUTES")
        print("=" * 70)

        route_count = 0
        for path, methods in paths.items():
            for method in methods.keys():
                route_count += 1
                print(f"  [{route_count:02d}] {method.upper():7s} {path}")

        print("-" * 70)
        print(f"  Total Validated Endpoints: {route_count}")

        # Step 2: Test live GET endpoints that don't need auth or params
        print("\n" + "=" * 70)
        print("   TESTING LIVE ENDPOINTS (GET requests)")
        print("=" * 70)

        get_endpoints = []
        for path, methods in paths.items():
            if "get" in methods:
                # Skip routes with path params like {project_id}
                if "{" not in path:
                    get_endpoints.append(path)

        for ep in sorted(get_endpoints):
            try:
                resp = client.get(ep)
                status = resp.status_code
                try:
                    body = resp.json()
                    # Truncate long responses
                    body_str = str(body)
                    if len(body_str) > 200:
                        body_str = body_str[:200] + "..."
                except Exception:
                    body_str = resp.text[:200] if resp.text else "(empty)"
                
                if status < 400:
                    tag = "OK"
                elif status == 401 or status == 403:
                    tag = "AUTH REQUIRED"
                elif status == 405:
                    tag = "METHOD CHECK"
                elif status == 422:
                    tag = "VALIDATION (expected)"
                else:
                    tag = "CHECK"

                print(f"  [{tag:20s}] GET {ep}")
                print(f"                       Status: {status} | Body: {body_str}")
                print()
            except Exception as e:
                print(f"  [ERROR             ] GET {ep}")
                print(f"                       {e}")
                print()

        # Step 3: Test POST endpoints (send empty body to see validation)
        print("=" * 70)
        print("   TESTING POST ENDPOINTS (empty body - validation check)")
        print("=" * 70)

        post_endpoints = []
        for path, methods in paths.items():
            if "post" in methods:
                if "{" not in path:
                    post_endpoints.append(path)

        for ep in sorted(post_endpoints):
            try:
                resp = client.post(ep, json={})
                status = resp.status_code
                try:
                    body = resp.json()
                    body_str = str(body)
                    if len(body_str) > 200:
                        body_str = body_str[:200] + "..."
                except Exception:
                    body_str = resp.text[:200] if resp.text else "(empty)"

                if status == 422:
                    tag = "VALIDATION OK"
                elif status == 401 or status == 403:
                    tag = "AUTH REQUIRED"
                elif status < 400:
                    tag = "OK"
                else:
                    tag = "CHECK"

                print(f"  [{tag:20s}] POST {ep}")
                print(f"                       Status: {status} | Body: {body_str}")
                print()
            except Exception as e:
                print(f"  [ERROR             ] POST {ep}")
                print(f"                       {e}")
                print()

        # Step 4: Test PUT endpoints
        print("=" * 70)
        print("   TESTING PUT ENDPOINTS (empty body - validation check)")
        print("=" * 70)

        put_endpoints = []
        for path, methods in paths.items():
            if "put" in methods:
                if "{" not in path:
                    put_endpoints.append(path)

        for ep in sorted(put_endpoints):
            try:
                resp = client.put(ep, json={})
                status = resp.status_code
                try:
                    body = resp.json()
                    body_str = str(body)
                    if len(body_str) > 200:
                        body_str = body_str[:200] + "..."
                except Exception:
                    body_str = resp.text[:200] if resp.text else "(empty)"

                if status == 422:
                    tag = "VALIDATION OK"
                elif status == 401 or status == 403:
                    tag = "AUTH REQUIRED"
                elif status < 400:
                    tag = "OK"
                else:
                    tag = "CHECK"

                print(f"  [{tag:20s}] PUT {ep}")
                print(f"                       Status: {status} | Body: {body_str}")
                print()
            except Exception as e:
                print(f"  [ERROR             ] PUT {ep}")
                print(f"                       {e}")
                print()

        print("=" * 70)
        print("   FULL TEST COMPLETE!")
        print("=" * 70)

if __name__ == "__main__":
    try:
        test_routes_verbose()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
