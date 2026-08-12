import os
import sys
from streamlit.web import cli as st_cli

def main():
    print("⚡ Initializing Elite Quant Engine Single-Vault Pre-Flight Checks...")
    
    # 1. Verify Python Version
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required.")
        sys.exit(1)
        
    # 2. Verify backend engine module exists
    engine_file = "elite_quant_engine.py"
    if not os.path.exists(engine_file):
        print(f"❌ Error: Required module file '{engine_file}' not found in current directory.")
        sys.exit(1)
        
    # 3. Verify frontend script exists
    target_script = "app.py"
    if not os.path.exists(target_script):
        print(f"❌ Error: Could not find frontend script '{target_script}'.")
        sys.exit(1)
        
    print("✅ All pre-flight checks passed successfully!")
    print(f"🚀 Launching Streamlit single-vault interface from {target_script}...")
    
    # Programmatically invoke streamlit run with headless settings
    sys.argv = ["streamlit", "run", target_script, "--server.headless=true"]
    sys.exit(st_cli.main())

if __name__ == "__main__":
    main()
