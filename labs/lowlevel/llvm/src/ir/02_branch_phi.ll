; 第二层：控制流与 phi。
;
; 运行：lli 02_branch_phi.ll   → 45
;
; 看三件事：
;   1. 每个 basic block（基本块）只有一个终结指令（br / ret），块内顺序执行；
;   2. 循环变量必须用 phi 汇合：phi 的前驱列表与 br 的来源块一一对应；
;   3. phi 的入值是"该前驱块结束时的值"，因此可以引用同一块里后定义的指令。

@.fmt = private unnamed_addr constant [4 x i8] c"%d\0A\00"

declare i32 @printf(ptr, ...)

; int sum_to(int n) { int acc = 0; for (int i = 0; i < n; ++i) acc += i; return acc; }
define i32 @sum_to(i32 %n) {
entry:
  br label %loop

loop:
  %i = phi i32 [ 0, %entry ], [ %i.next, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc.next, %loop ]
  %acc.next = add i32 %acc, %i
  %i.next = add i32 %i, 1
  %more = icmp slt i32 %i.next, %n
  br i1 %more, label %loop, label %exit

exit:
  ret i32 %acc.next
}

define i32 @main() {
entry:
  %total = call i32 @sum_to(i32 10)
  %ignored = call i32 (ptr, ...) @printf(ptr @.fmt, i32 %total)
  ret i32 0
}
