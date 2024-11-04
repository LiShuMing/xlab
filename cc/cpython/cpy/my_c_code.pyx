# my_c_code.pyx
cdef extern from "my_c_code.c":
    int c_sum(int a, int b)

def py_sum(int a, int b):
    return c_sum(a, b)