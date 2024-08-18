#include <Python.h>
#include <iostream>

// use python to calculate the square root of 9.0
int main() {
    Py_Initialize();

    if (!Py_IsInitialized()) {
        std::cerr << "Failed to initialize Python interpreter.\n";
        return -1;
    }

    PyRun_SimpleString("print('Hello from Python!')");

    // import math module
    PyObject* pModule = PyImport_ImportModule("math"); 
    // get sqrt function
    PyObject* pFunc = PyObject_GetAttrString(pModule, "sqrt"); 
    // call sqrt(9.0)
    PyObject* pValue = PyObject_CallFunction(pFunc, "(d)", 9.0); // 调用 sqrt(9.0)

    double result = PyFloat_AsDouble(pValue);
    std::cout << "Result of sqrt(9.0): " << result << std::endl;

    Py_Finalize();

    return 0;
}