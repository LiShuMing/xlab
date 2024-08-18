; Linux version (for Linux systems)
section .text
    global _start

_start:
    mov rcx, 10      ; counter
    xor rax, rax     ; sum = 0

.loop:
    add rax, rcx
    loop .loop       ; rcx--, if rcx != 0 then jump

    ; exit(sum)
    mov rdi, rax
    mov rax, 60
    syscall
