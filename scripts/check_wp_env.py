from pathlib import Path
import os
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env")
for k in ["WP_URL", "WP_USER", "WP_PASS"]:
    v = os.getenv(k)
    print(f"{k}={'set' if v else 'missing'} len={len(v) if v else 0}")
    if k == "WP_URL" and v:
        print("WP_URL=", v)
