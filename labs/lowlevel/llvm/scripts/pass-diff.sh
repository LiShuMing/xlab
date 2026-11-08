#!/usr/bin/env bash
# 逐个 pass 跑一遍，打印指令行数变化和 unified diff，用来回答"这个 pass 到底改了什么"。
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -lt 1 ]]; then
  echo "用法: scripts/pass-diff.sh <input.ll> [pass ...]" >&2
  echo "示例: scripts/pass-diff.sh src/ir/02_branch_phi.ll mem2reg instcombine" >&2
  exit 2
fi

opt=${OPT:-opt}
input=$1
shift
if [[ $# -gt 0 ]]; then
  passes=("$@")
else
  passes=(mem2reg instcombine gvn simplifycfg dce)
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# 先让 opt 重新打印一遍输入：注释与手写格式会被丢掉，后续 diff 只剩真正的 IR 变化。
"$opt" -passes=verify -S "$input" -o "$work/base.ll"

# 粗略计数：IR 的指令行都以两个空格缩进，块标签与注释不算。
count_instructions() { grep -cE '^  [^;]' "$1" || true; }

# ModuleID 与 source_filename 记录的是临时文件路径，逐 pass 变化，与优化无关。
strip_header() { grep -vE '^(; ModuleID|source_filename)' "$1"; }

echo "输入: $input"
for pass in "${passes[@]}"; do
  name=${pass//[^a-zA-Z0-9]/_}
  out="$work/$name.ll"
  if ! "$opt" -passes="$pass" -S "$work/base.ll" -o "$out" 2>"$work/err"; then
    printf '=== %-24s 运行失败: %s\n' "$pass" "$(tr '\n' ' ' <"$work/err")" >&2
    continue
  fi
  printf '\n=== %-24s 指令行 %s -> %s\n' "$pass" \
    "$(count_instructions "$work/base.ll")" "$(count_instructions "$out")"
  diff -u <(strip_header "$work/base.ll") <(strip_header "$out") | sed -n '3,$p' || true
done
