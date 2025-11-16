; ----------------------------------------------------------------------------
; 一个写入前90个斐波那契数字的64位Linux应用程序。至
; 编译汇编代码并运行：
;
; nasm -felf64 fib.asm && gcc fib.o && ./a.out
; ----------------------------------------------------------------------------

        global  main
        extern  printf

        section .text
main:
        push rbx                               ; 我们必须保存它,因为我们使用它

        mov ecx,90                             ; ecx将倒数至0
        xor rax,rax                            ; rax将保留当前数字
        xor rbx,rbx                            ; rbx将保留下一个数字
        inc rbx                                ; rbx最初是1
print:
        ; 我们需要调用printf,但是我们使用的是rax,rbx和rcx。打印
        ; 可能会破坏rax和rcx,因此我们将在调用之前保存它们,并且
        ; 之后恢复它们。

        push rax                               ; caller-save register
        push rcx                               ; caller-save register

        mov rdi,format                         ; 设置第一个参数(format)
        mov rsi,rax                            ; 设置第二个参数(current_number)
        xor rax,rax                            ; 因为printf是varargs

                                               ; 堆栈已经对齐,因为我们压入了三个8字节寄存器
        call printf                            ; printf(format, current_number)

        pop rcx                                ; restore caller-save register
        pop rax                                ; restore caller-save register

        mov rdx,rax                            ; save the current number
        mov rax,rbx                            ; next number is now current
        add rbx,rdx                            ; get the new next number
        dec ecx                                ; count down
        jnz print                              ; if not done counting, do some more

        pop rbx                                ; returing之前还原rbx
        
        ; exit(0)
        mov rax, 60                            ; sys_exit
        xor rdi, rdi                           ; exit code 0
        syscall
format:
        db  "%20ld",10,0
