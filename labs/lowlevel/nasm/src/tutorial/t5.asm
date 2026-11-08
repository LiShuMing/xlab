section .data
    nums dd 1,2,3,4,5,6,7,8

section .text
    global _start

_start:
    vmovdqu ymm0, [rel nums]   ; load 8 ints
    vphaddd ymm0, ymm0, ymm0   ; pairwise horizontal add
    vphaddd ymm0, ymm0, ymm0
    vphaddd ymm0, ymm0, ymm0
    movd eax, xmm0             ; result in eax

    mov rdi, rax
    mov rax, 60
    syscall