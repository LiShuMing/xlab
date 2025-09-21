; -------------------------------------------------- ---------------------------
; 一个用于计算x ^ y的64位命令行应用程序。
;
; 语法：power x y
; x和y均是(32位)整数
; -------------------------------------------------- ---------------------------

        global  main
        extern  printf
        extern  puts
        extern  atoi

        section .text
main:
        push    r12                     ; 调用者保存寄存器 
        push    r13
        push    r14
        ; 通过压入三个寄存器的值, 栈已经对齐 

        cmp     rdi, 3                  ; 必须有且仅有 2 个参数
        jne     error1

        mov     r12, rsi                ; argv

        ; 我们将使用 ecx 作为指数的计数器, 直至 ecx 减到 0。
        ; 使用 esi 来保存基数, 使用 eax 保存乘积。

        mov     rdi, [r12+16]           ; argv[2]
        call    atoi                    ; y in eax
        cmp     eax, 0                  ; 不允许负指数 
        jl      error2
        mov     r13d, eax               ; y in r13d

        mov     rdi, [r12+8]            ; argv
        call    atoi                    ; x in eax
        mov     r14d, eax               ; x in r14d

        mov     eax, 1                  ; 初始结果 start with answer = 1
check:
        test    r13d, r13d              ; 递减 y 直至 0
        jz      gotit                   ; done
        imul    eax, r14d               ; 再乘上一个 x
        dec     r13d
        jmp     check
gotit:                                  ; print report on success
        mov     rdi, answer
        movsxd  rsi, eax
        xor     rax, rax
        call    printf
        jmp     done
error1:                                 ; print error message
        mov     edi, badArgumentCount
        call    puts
        jmp     done
error2:                                 ; print error message
        mov     edi, negativeExponent
        call    puts
done:                                   ; restore saved registers
        pop     r14
        pop     r13
        pop     r12
        ret

answer:
        db      "%d", 10, 0
badArgumentCount:
        db      "Requires exactly two arguments", 10, 0
negativeExponent:
        db      "The exponent may not be negative", 10, 0
