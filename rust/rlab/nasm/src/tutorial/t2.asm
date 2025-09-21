section .text
    global _start

square:
    mov rax, rdi     ; rdi 传参
    imul rax, rax
    ret

_start:
    mov rdi, 7
    call square      ; rax = 49

    ; exit(rax)
    mov rdi, rax
    mov rax, 60
    syscall