import os
import re

routes_dir = r"d:\Satr_Edu_Ai\src\routes"
files = [f for f in os.listdir(routes_dir) if f.endswith(".py") and f != "__init__.py"]

all_routes = []

for filename in files:
    filepath = os.path.join(routes_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
        # Find prefix
        prefix_match = re.search(r'prefix\s*=\s*["\']([^"\']+)["\']', content)
        prefix = prefix_match.group(1) if prefix_match else ""
        
        # Find all routes
        # Matches @something_router.get("/path") or @router.get("/path")
        route_matches = re.finditer(r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']*)["\']', content)
        
        for match in route_matches:
            method = match.group(1).upper()
            path = match.group(2)
            full_path = f"{prefix}{path}"
            all_routes.append({
                "file": filename,
                "method": method,
                "path": full_path
            })

# Sort by path
all_routes.sort(key=lambda x: x["path"])

print(f"| Method | Route | File |")
print(f"| :--- | :--- | :--- |")
for r in all_routes:
    print(f"| {r['method']} | `{r['path']}` | {r['file']} |")
