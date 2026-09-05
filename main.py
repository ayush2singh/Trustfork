import os
import sys
import subprocess

def main():
    app_build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_build")
    cmd = ["uv", "run", "python", "main.py"]
    ret = subprocess.run(cmd, cwd=app_build_dir, shell=True)
    sys.exit(ret.returncode)

if __name__ == "__main__":
    main()
