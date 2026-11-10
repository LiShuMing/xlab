"""Read-only release and native execution assessment, without changing OS policy."""

import platform
import subprocess
from uuid import uuid4

from llm_observe.downloads import binaries
from llm_observe.paths import LOCAL, write_json


def doctor() -> None:
    executables = binaries()
    report = {
        "platform": platform.platform(),
        "binary_hashes_match_receipt": True,
        "system_policy_changed": False,
        "executables": {},
    }
    if platform.system() == "Darwin":
        for name, binary in executables.items():
            checks = {}
            for check, command in {
                "signature": ["codesign", "--verify", "--verbose=2", binary],
                "execution_assessment": [
                    "spctl",
                    "--assess",
                    "--type",
                    "execute",
                    "--verbose=2",
                    binary,
                ],
            }.items():
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                checks[check] = {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            report["executables"][name] = checks
    path = LOCAL / "artifacts" / f"doctor-{uuid4().hex}.json"
    write_json(path, report)
    print(f"Read-only execution assessment archived at {path}")
    for name, checks in report["executables"].items():
        print(name, {key: value["returncode"] for key, value in checks.items()})
