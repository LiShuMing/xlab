#!/usr//bin/python3

import os
import subprocess
import sys

from tools import run_command
from tools import get_submodule_git_url

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_submodule.py <parent_project_path> <subproject_path> [<submodule_name>]")
        sys.exit(1)

    subproject_path = sys.argv[1]
    get_submodule_git_url(subproject_path)