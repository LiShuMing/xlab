; 示例：简单的数据移动操作
section .data
    message db 'Hello, Assembly!', 0xA  ; 定义字符串数据
    length equ $ - message             ; 计算字符串长度

section .text
    global _start

_start:
    ; 系统调用: write(1, message, length)
    mov eax, 4        ; syscall number for write
    mov ebx, 1        ; file descriptor (stdout)
    mov ecx, message  ; pointer to message
    mov edx, length   ; message length
    int 0x80          ; invoke kernel

    ; 系统调用: exit(0)
    mov eax, 1        ; syscall number for exit
    xor ebx, ebx      ; return code 0
    int 0x80