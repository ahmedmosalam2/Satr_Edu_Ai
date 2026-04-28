"""Inspect the downloaded surya_rec2 config.json structure."""
import json
import glob
import os

cache_dir = os.path.expanduser("~/.cache/huggingface/hub")

print("=== Searching for surya_rec2 config ===")
patterns = [
    f"{cache_dir}/models--vikp--surya_rec2/snapshots/*/config.json",
    f"{cache_dir}/models--vikp--surya_rec*/snapshots/*/config.json",
]
for pattern in patterns:
    for path in glob.glob(pattern):
        print(f"\nFound: {path}")
        with open(path) as f:
            config = json.load(f)
        print(f"Top-level keys: {list(config.keys())}")
        print(f"\nFull config (first 3000 chars):")
        print(json.dumps(config, indent=2)[:3000])
        break

print("\n\n=== surya pip version ===")
try:
    import pkg_resources
    for pkg in ["surya-ocr", "surya"]:
        try:
            ver = pkg_resources.get_distribution(pkg).version
            print(f"{pkg}: {ver}")
        except Exception:
            pass
except Exception:
    pass

try:
    import surya
    print(f"surya.__version__: {getattr(surya, '__version__', 'N/A')}")
    print(f"surya location: {surya.__file__}")
except Exception as e:
    print(f"surya import: {e}")

print("\n=== transformers version ===")
try:
    import transformers
    print(f"transformers: {transformers.__version__}")
except Exception:
    pass
