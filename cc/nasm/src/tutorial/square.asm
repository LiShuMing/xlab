section .text
    global square
square:
    mov rax, rdi
    imul rax, rax
    ret