#!/usr//bin/python3

import os
import subprocess
import sys

from tools import run_command
from tools import get_submodule_git_url
from tools import add_submodule

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python add_submodule.py <parent_project_path> <subproject_path> [<submodule_name>]")
        sys.exit(1)

    parent_path = sys.argv[1]
    subproject_path = sys.argv[2]
    submodule_name = sys.argv[3] if len(sys.argv) > 3 else None

    add_submodule(parent_path, subproject_path, submodule_name)