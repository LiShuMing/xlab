#include <stdio.h>

// Declaration for ARM64 assembly function
extern int sum_1_to_10(void);

int main() {
    int result = sum_1_to_10();
    printf("Sum = %d\n", result);
    return 0;
}
