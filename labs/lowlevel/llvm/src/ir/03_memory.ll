; 第三层：内存。alloca 分配栈槽，GEP（GetElementPtr）只算地址，load/store 才读写。
;
; 运行：lli 03_memory.ll   → 36
;
; 这一段等价于：
;   int buf[8];
;   for (int i = 0; i < 8; ++i) buf[i] = i + 1;
;   return buf 全部元素之和;   // 1 + 2 + ... + 8 = 36
;
; 看三件事：
;   1. GEP 从不访存，它只做"基址 + 偏移"的地址运算，且偏移按元素类型自动缩放；
;   2. 数组的 GEP 有两个下标：第一个跨数组（这里恒为 0），第二个才是元素下标；
;   3. 用指针做循环变量时 phi 的类型是 ptr，与整型循环变量的写法完全对称。

define i32 @fill_and_sum() {
entry:
  %buf = alloca [8 x i32], align 16
  %base = getelementptr inbounds [8 x i32], ptr %buf, i64 0, i64 0
  %end = getelementptr inbounds [8 x i32], ptr %buf, i64 0, i64 8
  br label %init

init:
  %p = phi ptr [ %base, %entry ], [ %p.next, %init ]
  %v = phi i32 [ 1, %entry ], [ %v.next, %init ]
  store i32 %v, ptr %p, align 4
  %p.next = getelementptr inbounds i32, ptr %p, i64 1
  %v.next = add i32 %v, 1
  %last = icmp eq ptr %p.next, %end
  br i1 %last, label %sum.entry, label %init

sum.entry:
  br label %sum

sum:
  %q = phi ptr [ %base, %sum.entry ], [ %q.next, %sum ]
  %acc = phi i32 [ 0, %sum.entry ], [ %acc.next, %sum ]
  %cur = load i32, ptr %q, align 4
  %acc.next = add i32 %acc, %cur
  %q.next = getelementptr inbounds i32, ptr %q, i64 1
  %done = icmp eq ptr %q.next, %end
  br i1 %done, label %exit, label %sum

exit:
  ret i32 %acc.next
}

@.fmt = private unnamed_addr constant [4 x i8] c"%d\0A\00"

declare i32 @printf(ptr, ...)

define i32 @main() {
entry:
  %total = call i32 @fill_and_sum()
  %ignored = call i32 (ptr, ...) @printf(ptr @.fmt, i32 %total)
  ret i32 0
}
