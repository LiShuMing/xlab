#!/usr//bin/python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

from tools import run_command
from tools import get_submodule_git_url
from tools import add_submodule

def parent_dir(directory):
    return os.path.dirname(directory)

def get_changed_directories():
    try:
        # result = subprocess.run(
        #     ["git", "status", "--porcelain"],
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE,
        #     text=True,
        #     check=True
        # )
        result = run_command(["git", "status", "--porcelain"])
        # print(result)
        changed_files = result.splitlines()

        changed_dirs = set()
        for line in changed_files:
            # print("line:", line)
            parts = line.strip().split(maxsplit=1)
            # print(parts[1])
            change_path = os.path.abspath(parts[1])
            # print("path:", change_path)
            # print(change_path)
            if os.path.isdir(change_path):
                changed_dirs.add(change_path)
            # parts = line.strip().split(maxsplit=1)
            # if len(parts) > 1:
            #     file_path = parts[1]
            #     directory = file_path.split("/")[0]  
            #     changed_dirs.add(directory)
            # break
        return sorted(changed_dirs)
    except subprocess.CalledProcessError as e:
        print("Error running git command:", e.stderr)
        return []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pytools.py <commond_name> <commond argument...>]")
        sys.exit(1)
    commond_name = sys.argv[1]

    if commond_name == "get_changed_directories":
        result = get_changed_directories()
        print(result)
        for dir in result:
            if "/cc/" in dir:
                if "seastar" in dir:
                    continue
                print(dir)
                add_submodule('.', dir, "cc/thirdparty/" + os.path.basename(dir))
            elif "/python/" in dir:
                # if "thirdparty" in dir:
                #     continue
                # print(dir)
                # add_submodule('.', dir, "python/thirdparty/" + os.path.basename(dir))
                continue
    else:
        print("commond not found")
        sys.exit(1)