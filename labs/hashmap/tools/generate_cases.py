"""Generate fixed keys once for both runtime tables and compile-time perfect tables."""

import argparse
import json
from pathlib import Path
import random

CASES = [
    ("short8", 8, 8),
    ("short64", 64, 8),
    ("short255", 255, 8),
    ("short256", 256, 8),
    ("short1024", 1024, 8),
    ("prefix64", 64, 48),
]


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    data = [
        "#pragma once",
        "#include <array>",
        "#include <string_view>",
        "#include <cstdint>",
        "namespace hashmap_lab::data {",
    ]
    perfect = [
        '#include "bench/bench.h"',
        '#include "cases.h"',
        '#include "perfect_hash.h"',
        "namespace hashmap_lab {",
        "namespace {",
    ]
    names = []
    for name, count, length in CASES:
        rng = random.Random(20261108 + count + length)
        keys = []
        while len(keys) < count:
            suffix = f"{rng.getrandbits(28):07x}"
            key = "k" + suffix if length == 8 else "shared-prefix-" + "x" * 27 + suffix
            if key not in keys:
                keys.append(key)
        assert all(len(k) == length for k in keys)
        values = ",".join(str(i + 1) for i in range(count))
        data.extend(
            [
                f"inline constexpr std::array<std::string_view, {count}> {name}_keys{{{{",
                ",\n".join(json.dumps(key) for key in keys),
                "}};",
                f"inline constexpr std::array<std::uint32_t, {count}> {name}_values"
                + "{"
                + values
                + "};",
            ]
        )
        if count <= 255:
            perfect.extend(
                [
                    f"constexpr auto {name}_plan = ConstexprCore::compute_phf(data::{name}_keys);",
                    f"constexpr ConstexprCore::perfect_hash_map<{count}, std::uint32_t, "
                    f"{name}_plan.table_size, {length}> {name}_map"
                    f"{{data::{name}_keys, data::{name}_values, {name}_plan}};",
                ]
            )
        else:
            perfect.append(
                f"constexpr auto {name}_map = "
                f"ConstexprCore::make_wide_perfect_map<data::{name}_keys, data::{name}_values>();"
            )
        if name in ("short8", "short64"):
            perfect.append(
                f"constexpr auto {name}_wide = "
                f"ConstexprCore::make_wide_perfect_map<data::{name}_keys, data::{name}_values>();"
            )
        names.append(name)
    data.extend(
        [
            "}",
            "namespace hashmap_lab {",
            "inline std::vector<std::string> FixedKeys(const std::string& name) {",
        ]
    )
    for name in names:
        data.append(
            f'    if (name == "{name}") return '
            f"{{data::{name}_keys.begin(), data::{name}_keys.end()}};"
        )
    data.extend(['    throw std::invalid_argument("unknown fixed case: " + name);', "}", "}"])
    perfect.extend(
        ["}", "void RunPerfect(const Options& options, const Dataset<std::string_view>& data) {"]
    )
    for name in names:
        if name in ("short8", "short64"):
            perfect.append(
                f'    if (options.case_name == "{name}" && options.method == "wide") '
                f"{{ RunPerfectLookup({name}_wide, options, data); return; }}"
            )
        perfect.append(
            f'    if (options.case_name == "{name}" && options.method == "perfect") '
            f"{{ RunPerfectLookup({name}_map, options, data); return; }}"
        )
    perfect.extend(
        ['    throw std::invalid_argument("perfect strategy unavailable for this case");', "}", "}"]
    )
    (output / "cases.h").write_text("\n".join(data) + "\n")
    (output / "perfect_cases.cc").write_text("\n".join(perfect) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    generate(parser.parse_args().output)
