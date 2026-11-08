"""Controlled aggregate state layouts and initialization API comparisons."""

import itertools


def jobs(config: dict) -> list[dict]:
    result = []
    for scenario in config["scenarios"]:
        for state_bytes, distribution, seed, method in itertools.product(
            config["state_bytes"], scenario["distributions"], config["seeds"], config["methods"]
        ):
            result.append(
                {
                    "case": scenario["case"],
                    "n": scenario["n"],
                    "ndv": scenario["ndv"],
                    "null-percent": scenario["null_percent"],
                    "state-bytes": state_bytes,
                    "distribution": distribution,
                    "seed": seed,
                    "method": method,
                }
            )
    return result
