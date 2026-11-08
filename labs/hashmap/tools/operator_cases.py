"""Operator scenarios, with explicit semantic eligibility for every strategy."""

import itertools


def jobs(config):
    result = []
    for scenario in config["scenarios"]:
        modes = scenario.get("modes", ["aggregate"])
        hits = scenario.get("hits", [50])
        for mode, hit, distribution, seed, method in itertools.product(
            modes, hits, scenario["distributions"], config["seeds"], scenario["methods"]
        ):
            result.append(
                dict(
                    case=scenario["case"],
                    n=scenario["n"],
                    ndv=scenario["ndv"],
                    domain=scenario["domain"],
                    null_percent=scenario["null_percent"],
                    mode=mode,
                    hit=hit,
                    distribution=distribution,
                    seed=seed,
                    method=method,
                    load=0.75,
                )
            )
    # CLI spelling stays uniform with the generic runner.
    for job in result:
        job["null-percent"] = job.pop("null_percent")
    return result
