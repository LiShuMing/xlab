#!/usr/bin/env bash
# 断言三层产物真的对：手写 IR 跑出预期结果、clang 生成的 IR 合法、自写 pass 改变了 IR。
set -euo pipefail

cd "$(dirname "$0")/.."

lli=${LLI:-lli}
opt=${OPT:-opt}

failures=0

ok() { printf '  ok    %s\n' "$1"; }
bad() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }

# 手写 IR 用返回值断言最干净：退出码不受 printf 缓冲影响。
expect_exit() {
  local ir=$1 want=$2 rc=0
  "$lli" "$ir" >/dev/null 2>&1 || rc=$?
  if [[ $rc -eq $want ]]; then
    ok "$(basename "$ir") 退出码 $rc"
  else
    bad "$(basename "$ir") 期望退出码 $want，实得 $rc"
  fi
}

expect_stdout() {
  local ir=$1 want=$2 out
  if ! out=$("$lli" "$ir" 2>/dev/null); then
    bad "$(basename "$ir") lli 执行失败"
    return
  fi
  if [[ $out == *"$want"* ]]; then
    ok "$(basename "$ir") 输出 $out"
  else
    bad "$(basename "$ir") 输出 $out，缺少 $want"
  fi
}

echo '== 手写 IR 的执行结果 =='
expect_exit src/ir/01_basics.ll 42
expect_stdout src/ir/02_branch_phi.ll 45
expect_stdout src/ir/03_memory.ll 36
expect_stdout src/ir/04_loop_invariant.ll 945

echo '== clang 生成的 IR 通过 verify =='
for ir in bin/clang/*.ll; do
  if "$opt" -passes=verify -disable-output "$ir" 2>/dev/null; then
    ok "$(basename "$ir")"
  else
    bad "$(basename "$ir") verify 失败"
  fi
done

echo '== 自写 pass 生效 =='
stats=$("$opt" -load-pass-plugin=bin/passes/IrStats.so -passes=ir-stats -disable-output \
  src/ir/04_loop_invariant.ll 2>&1) || true
if [[ $stats == *"[ir-stats] scale_sum"* ]]; then
  ok "ir-stats 统计到 scale_sum"
else
  bad "ir-stats 没有输出 scale_sum 的统计"
fi

shifted=$("$opt" -load-pass-plugin=bin/passes/MulToShift.so -passes=mul-to-shift -S \
  src/ir/01_basics.ll -o - 2>/dev/null) || true
if [[ $shifted == *"shl i32 %sum, 1"* && $shifted != *"mul i32 %sum, 2"* ]]; then
  ok "mul-to-shift 把 mul 2 换成了 shl 1"
else
  bad "mul-to-shift 没有按预期改写 01_basics.ll"
fi

# 改写后的 IR 仍要能跑出同一个结果，否则说明 pass 改错了语义。
tmp=$(mktemp)
"$opt" -load-pass-plugin=bin/passes/MulToShift.so -passes=mul-to-shift -S \
  src/ir/01_basics.ll -o "$tmp" 2>/dev/null
rc=0
"$lli" "$tmp" >/dev/null 2>&1 || rc=$?
rm -f "$tmp"
if [[ $rc -eq 42 ]]; then
  ok "改写后的 01_basics.ll 仍返回 42"
else
  bad "改写后的 01_basics.ll 返回 $rc，语义被破坏"
fi

echo
if [[ $failures -ne 0 ]]; then
  printf '失败 %d 项\n' "$failures" >&2
  exit 1
fi
echo '全部通过'
