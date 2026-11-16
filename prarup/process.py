import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_tool(name):
    local = (Path(sys.executable).parent, Path(sys.prefix) / name)
    return shutil.which(name) or shutil.which(name, path=os.pathsep.join(map(str, local)))


def run_tool(args, *, cwd=None, input=None, errors="strict"):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    return subprocess.run(
        args, cwd=cwd, input=input, capture_output=True,
        encoding="utf-8", errors=errors, creationflags=flags,
    )
