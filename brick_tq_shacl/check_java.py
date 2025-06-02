import subprocess
import sys

def check_java_installed():
    try:
        subprocess.run(["java", "-version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("Java is not installed. Please install Java to use this package.")

if __name__ == "__main__":
    check_java_installed()
