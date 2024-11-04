// my_c_extension.c
#include <Python.h>

// 实现 C 函数
int c_sum(int a, int b) {
    return a + b;
}

// Python 包装函数
static PyObject* py_c_sum(PyObject* self, PyObject* args) {
    int a, b;
    if (!PyArg_ParseTuple(args, "ii", &a, &b)) {
        return NULL;
    }
    int result = c_sum(a, b);
    return PyLong_FromLong(result);
}

// 定义方法列表
static PyMethodDef MyMethods[] = {
    {"c_sum", py_c_sum, METH_VARARGS, "Calculate sum of two integers"},
    {NULL, NULL, 0, NULL}
};

// 定义模块
static struct PyModuleDef my_c_extension_module = {
    PyModuleDef_HEAD_INIT,
    "my_c_extension",  // 模块名
    NULL,
    -1,
    MyMethods
};

// 初始化模块
PyMODINIT_FUNC PyInit_my_c_extension(void) {
    return PyModule_Create(&my_c_extension_module);
}