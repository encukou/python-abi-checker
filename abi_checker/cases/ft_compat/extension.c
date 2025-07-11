/*
Example module from PEP 793, further modified for compatibility
*/

// Require opaque PyObject (if available)
#define Py_OPAQUE_PYOBJECT
#define _Py_OPAQUE_PYOBJECT

#include <Python.h>

#define FTCOMPAT_MODNAME extension
#include "ft_compat.h"

typedef struct {
    int value;
} extension_state;

static PyObject *
increment_value(PyObject *module, PyObject *_ignored)
{
    extension_state *state = PyModule_GetState(module);
    int result = ++(state->value);
    return PyLong_FromLong(result);
}

static PyMethodDef extension_methods[] = {
    {"increment_value", increment_value, METH_NOARGS},
    {NULL}
};

static int
extension_exec(PyObject *module) {
    extension_state *state = PyModule_GetState(module);
    state->value = -1;
    return 0;
}

PyDoc_STRVAR(extension_doc, "Example extension.");

static PyModuleDef_Slot extension_slots[] = {
    {Py_mod_name, "extension"},
    {Py_mod_doc, (char*)extension_doc},
    {Py_mod_methods, extension_methods},
    {Py_mod_state_size, (void*)sizeof(extension_state)},
    {Py_mod_exec, (void*)extension_exec},
    {0}
};

// Avoid "implicit declaration of function" warning:
PyMODEXPORT_FUNC PyModExport_extension(PyObject *);

PyMODEXPORT_FUNC
PyModExport_extension(PyObject *spec)
{
    return extension_slots;
}

