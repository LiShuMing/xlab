; 第四层：为优化 pass 准备素材。
;
; 运行：lli 04_loop_invariant.ll   → 945
;
; 循环体里有两类乘法：
;   %k = mul i32 %factor, 7    每轮都算同一个值 → licm 应该把它提到循环外；
;   %v = mul i32 %i, %k        依赖循环变量 → 只能留在循环内。
;
; 再看 %i 与 %acc：这两个 phi 的形状正是 mem2reg 之后循环变量的标准形态，
; opt 的 indvars（归纳变量化简）会在此基础上继续改造。
;
; 运行：make passes 会把它逐个 pass 前后对比。

define i32 @scale_sum(i32 %n, i32 %factor) {
entry:
  br label %loop

loop:
  %i = phi i32 [ 0, %entry ], [ %i.next, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc.next, %loop ]
  %k = mul i32 %factor, 7
  %v = mul i32 %i, %k
  %acc.next = add i32 %acc, %v
  %i.next = add i32 %i, 1
  %more = icmp slt i32 %i.next, %n
  br i1 %more, label %loop, label %exit

exit:
  ret i32 %acc.next
}

@.fmt = private unnamed_addr constant [4 x i8] c"%d\0A\00"

declare i32 @printf(ptr, ...)

define i32 @main() {
entry:
  ; 3 * 7 * (0 + 1 + ... + 9) = 21 * 45 = 945
  %total = call i32 @scale_sum(i32 10, i32 3)
  %ignored = call i32 (ptr, ...) @printf(ptr @.fmt, i32 %total)
  ret i32 0
}
