#!/usr//bin/python3

import os
import subprocess
import sys

def run_command(command, cwd=None):
    """
    Helper function to run a shell command and return its output.
    """
    try:
        print("Running command:", " ".join(command))
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.stderr.strip()}")
        raise e

def get_submodule_git_url(subproject_path):
    # Ensure paths are absolute
    subproject_path = os.path.abspath(subproject_path)
    # Check if subproject is a valid Git repository
    if not os.path.exists(os.path.join(subproject_path, ".git")):
        print(f"Error: {subproject_path} is not a valid Git repository.")
        raise RuntimeError(f"{subproject_path} is not a valid Git repository.")

    # Get the remote URL of the subproject
    subproject_url = run_command(["git", "remote", "get-url", "origin"], cwd=subproject_path)
    print(f"Submodule URL: {subproject_url}")
    return subproject_url

def add_submodule(parent_project_path, subproject_path, submodule_name=None):
    """
    Add a local Git project as a submodule to a parent Git project.
    """
    # Ensure paths are absolute
    parent_project_path = os.path.abspath(parent_project_path)
    subproject_path = os.path.abspath(subproject_path)
    print("parent_project_path:", parent_project_path)
    print("subproject_path:", subproject_path)

    # Check if parent project is a valid Git repository
    if not os.path.exists(os.path.join(parent_project_path, ".git")):
        print(f"Error: {parent_project_path} is not a valid Git repository.")
        raise RuntimeError("{parent_project_path} is not a valid Git repository.")

    # Get the remote URL of the subproject
    subproject_url = get_submodule_git_url(subproject_path)

    # Determine submodule name or use default
    if submodule_name:
        if os.path.basename(subproject_path) != os.path.basename(submodule_name):
            submodule_name = os.path.join(submodule_name, os.path.basename(subproject_path))
    else:
        submodule_name = os.path.basename(subproject_path)

    # Add the submodule to the parent project
    run_command(["git", "submodule", "add", subproject_url, submodule_name], cwd=parent_project_path)

    # Commit the changes to the parent project
    run_command(["git", "add", ".gitmodules", submodule_name], cwd=parent_project_path)
    run_command(["git", "commit", "-m", f"Added submodule {submodule_name}"], cwd=parent_project_path)

    print(f"Successfully added {submodule_name} as a submodule to {parent_project_path}.")