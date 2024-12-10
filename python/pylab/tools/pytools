#!/usr//bin/python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
from typing import List


from tools import run_command
from tools import get_submodule_git_url
from tools import add_submodule

def parent_dir(directory):
    return os.path.dirname(directory)

def list_dir(path:str) -> List[str]:
    directories = []
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            abspath = os.path.abspath(full_path)
            directories.append(abspath)
    return directories

def get_changed_directories():
    try:
        result = run_command(["git", "status", "--porcelain"])
        changed_files = result.splitlines()

        changed_dirs = set()
        for line in changed_files:
            parts = line.strip().split(maxsplit=1)
            change_path = os.path.abspath(parts[1])
            if os.path.isdir(change_path):
                changed_dirs.add(change_path)
        return sorted(changed_dirs)
    except subprocess.CalledProcessError as e:
        print("Error running git command:", e.stderr)
        return []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pytools.py <commond_name> <commond argument...>]")
        sys.exit(1)
    command_name = sys.argv[1]

    if command_name == "get_changed_directories":
        result = get_changed_directories()
        print(result)
        for dir in result:
            if "/cc/" in dir:
                if "seastar" in dir:
                    continue
                add_submodule('.', dir, "cc/thirdparty/" + os.path.basename(dir))
    elif command_name == "list_dir":
        cur_dir = sys.argv[2]
        thirdparty_dir = sys.argv[3]
        print("cur_dir:", cur_dir)
        print("thirdparty_dir:", thirdparty_dir)

        result = list_dir(cur_dir)
        for directory in result:
            print(directory)
            url = get_submodule_git_url(directory)
            print(url)
            try:
                add_submodule(".", directory, thirdparty_dir)
            except Exception as e:
                print("Add module failed:" + str(e))
                continue
    else:
        print("commond not found")
        sys.exit(1)