// /**
//  * 1. apt install libunwind-dev
//  * 2. maybe use code : https://github.com/apache/doris/pull/21755/files#
//  */
#include <libunwind.h>
#include <iostream>

void printStackTrace() {
    // unw_cursor_t cursor;
    // unw_context_t context;

    // // 初始化上下文和游标
    // unw_getcontext(&context);
    // // unw_init_local(&cursor, &context);

    // std::cout << "Stack trace:" << std::endl;

    // // 遍历栈帧
    // while (unw_step(&cursor) > 0) {
    //     char funcName[256];
    //     unw_word_t offset, pc;

    //     // 获取当前栈帧的程序计数器（PC）
    //     unw_get_reg(&cursor, UNW_REG_IP, &pc);

    //     // 获取函数名和偏移量
    //     if (unw_get_proc_name(&cursor, funcName, sizeof(funcName), &offset) == 0) {
    //         std::cout << "  0x" << std::hex << pc << ": " << funcName << "+0x" << offset << std::endl;
    //     } else {
    //         std::cout << "  0x" << std::hex << pc << ": ???" << std::endl;
    //     }
    // }
}

int main() {
    printStackTrace();
}