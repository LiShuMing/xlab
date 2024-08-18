section .data
    msg db "NASM Assembly!", 0

section .text
    global _start

strlen:
    xor rcx, rcx
.loop:
    cmp byte [rdi+rcx], 0
    je .done
    inc rcx
    jmp .loop
.done:
    mov rax, rcx
    ret

_start:
    mov rdi, msg
    call strlen

    ; exit(length)
    mov rdi, rax
    mov rax, 60
    syscall