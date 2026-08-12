import os
import sys
from streamlit.web import cli as st_cli

def main():
    print("⚡ Initializing Elite Quant Engine Pre-Flight Checks...")
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required.")
        sys.exit(1)
        
    for f in ["database.py", "elite_quant_engine.py", "app.py"]:
        if not os.path.exists(f):
            print(f"❌ Error: Required file '{f}' not found.")
            sys.exit(1)
            
    print("✅ All pre-flight checks passed successfully!")
    sys.argv = ["streamlit", "run", "app.py", "--server.headless=true"]
    sys.exit(st_cli.main())

if __name__ == "__main__":
    main()
