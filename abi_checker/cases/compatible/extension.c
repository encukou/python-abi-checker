/*
Example module from PEP 793, further modified for compatibility
*/

// Avoid CPython-version-specific ABI (inline functions & macros):
#ifndef Py_GIL_DISABLED
#define Py_LIMITED_API 0x03090000
#endif

#include <Python.h>
#include <ft_compat.h>

typedef struct {
    int value;
} examplemodule_state;

static PyObject *
increment_value(PyObject *module, PyObject *_ignored)
{
    examplemodule_state *state = PyModule_GetState(module);
    int result = ++(state->value);
    return PyLong_FromLong(result);
}

static PyMethodDef examplemodule_methods[] = {
    {"increment_value", increment_value, METH_NOARGS},
    {NULL}
};

static int
examplemodule_exec(PyObject *module) {
    examplemodule_state *state = PyModule_GetState(module);
    state->value = -1;
    return 0;
}

PyDoc_STRVAR(examplemodule_doc, "Example extension.");

static PyModuleDef_Slot examplemodule_slots[] = {
    {Py_mod_name, "examplemodule"},
    {Py_mod_doc, (char*)examplemodule_doc},
    {Py_mod_methods, examplemodule_methods},
    {Py_mod_state_size, (void*)sizeof(examplemodule_state)},
    {Py_mod_exec, (void*)examplemodule_exec},
    {0}
};

// Avoid "implicit declaration of function" warning:
PyMODEXPORT_FUNC PyModExport_examplemodule(PyObject *);

PyMODEXPORT_FUNC
PyModExport_examplemodule(PyObject *spec)
{
    return examplemodule_slots;
}
