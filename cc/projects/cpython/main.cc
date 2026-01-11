#include <Python.h>
#include <iostream>

int main() {
    Py_Initialize();

    if (!Py_IsInitialized()) {
        std::cerr << "Failed to initialize Python interpreter.\n";
        return -1;
    }

    PyRun_SimpleString("print('Hello from Python!')");

    PyObject* pModule = PyImport_ImportModule("math"); // 导入 math 模块
    PyObject* pFunc = PyObject_GetAttrString(pModule, "sqrt"); // 获取 sqrt 函数
    PyObject* pValue = PyObject_CallFunction(pFunc, "(d)", 9.0); // 调用 sqrt(9.0)

    double result = PyFloat_AsDouble(pValue);
    std::cout << "Result of sqrt(9.0): " << result << std::endl;

    Py_Finalize();

    return 0;
}