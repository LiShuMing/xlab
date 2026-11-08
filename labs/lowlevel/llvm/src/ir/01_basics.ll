; 第一层：类型、常量、参数、算术指令、函数调用。
;
; 运行：lli 01_basics.ll; echo $?   → 42
;
; 看三件事：
;   1. 每条指令都显式写出类型，IR 里没有隐式类型提升；
;   2. SSA（Static Single Assignment，静态单赋值）：%sum 只被赋值一次，
;      想改值只能产生新名字，不能原地覆盖；
;   3. 标量局部变量不需要 alloca，值直接在寄存器里流动。

define i32 @add_mul(i32 %a, i32 %b) {
entry:
  %sum = add i32 %a, %b
  %prod = mul i32 %sum, 2
  %sub = sub i32 %prod, %a
  ret i32 %sub
}

define i32 @main() {
entry:
  ; (10 + 16) * 2 - 10 = 42，退出码留作断言
  %r = call i32 @add_mul(i32 10, i32 16)
  ret i32 %r
}
