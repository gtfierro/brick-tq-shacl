from . import topquadrant_shacl
__version__ = "0.3.4a2"
__all__ = ["topquadrant_shacl"]


def check_java_installed():
    import subprocess
    import sys
    try:
        subprocess.run(["java", "-version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("Java is not installed. Please install Java to use this package.")


check_java_installed()
