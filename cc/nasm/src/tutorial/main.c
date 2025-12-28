#include "stdio.h"

long square(long);
long my_write(long fd, const char *buf, long len);


int main() {
    // printf("%ld\n", square(12));
    my_write(1, "Hello, world!\n", 13);
    return 0;
}