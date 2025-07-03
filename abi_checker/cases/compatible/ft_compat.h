#include <string.h>     // memset

#ifndef PyMODINIT_FUNC
#error "This header must pe included after Python.h"
#endif

#ifndef Py_mod_name
#define Py_mod_name 5
#define Py_mod_doc 6
#define Py_mod_state_size 7
#define Py_mod_methods 8
#define Py_mod_state_traverse 9
#define Py_mod_state_clear 10
#define Py_mod_state_free 11
#define Py_mod_token 12
#define PyMODEXPORT_FUNC extern __attribute__ ((visibility ("default"))) PyModuleDef_Slot*
#endif

struct pyobject_compat_gil {
    alignas(Py_ssize_t) alignas(4) Py_ssize_t ob_refcnt;
    PyTypeObject *ob_type;
};

struct pyobject_compat_ft {
    // ob_tid stores the thread id (or zero). It is also used by the GC and the
    // trashcan mechanism as a linked list pointer and by the GC to store the
    // computed "gc_refs" refcount.
    alignas(uintptr_t) alignas(4) uintptr_t ob_tid;
    uint16_t ob_flags;
    char /* PyMutex */ ob_mutex;
    uint8_t ob_gc_bits;
    uint32_t ob_ref_local;
    Py_ssize_t ob_ref_shared;
    PyTypeObject *ob_type;
};

struct PyModuleDef_Base_compat_gil {
    struct pyobject_compat_gil ob_base;
    PyObject* (*m_init)(void);
    Py_ssize_t m_index;
    PyObject* m_copy;
};

struct PyModuleDef_Base_compat_ft {
    struct pyobject_compat_ft ob_base;
    PyObject* (*m_init)(void);
    Py_ssize_t m_index;
    PyObject* m_copy;
};

struct PyModuleDef_compat_gil {
    struct PyModuleDef_Base_compat_gil m_base;
    const char* m_name;
    const char* m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    PyModuleDef_Slot *m_slots;
    traverseproc m_traverse;
    inquiry m_clear;
    freefunc m_free;
};

struct PyModuleDef_compat_ft {
    struct PyModuleDef_Base_compat_ft m_base;
    const char* m_name;
    const char* m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    PyModuleDef_Slot *m_slots;
    traverseproc m_traverse;
    inquiry m_clear;
    freefunc m_free;
};

union PyModuleDef_compat_both {
    struct PyModuleDef_compat_gil def_gil;
    struct PyModuleDef_compat_ft def_ft;
};

PyMODEXPORT_FUNC PyModExport_examplemodule(PyObject *);

PyMODINIT_FUNC PyInit_examplemodule(void);

PyMODINIT_FUNC
PyInit_extension(void)
{
    static union PyModuleDef_compat_both module_def_and_token;
    static int is_set_up;

    PyModuleDef_Slot *slot = PyModExport_examplemodule(NULL);

    if (is_set_up) {
        // Take care to only set up the static PyModuleDef once.
        // (PyModExport might theoretically return different data each time.)
        return PyModuleDef_Init((void*)&module_def_and_token);
    }
    int copying_slots = 1;
    for (/* slot set above */; slot->slot; slot++) {
        switch (slot->slot) {
        // Set PyModuleDef members from slots. These slots must come first.
#       define COPYSLOT_CASE(SLOT, MEMBER, TYPE)                            \
            case SLOT:                                                      \
                if (!copying_slots) {                                       \
                    PyErr_SetString(PyExc_SystemError,                      \
                                    #SLOT " must be specified earlier");    \
                    goto error;                                             \
                }                                                           \
                module_def_and_token.def_gil.MEMBER = (TYPE)(slot->value);  \
                break;                                                      \
            /////////////////////////////////////////////////////////////////
        COPYSLOT_CASE(Py_mod_name, m_name, char*)
        COPYSLOT_CASE(Py_mod_doc, m_doc, char*)
        COPYSLOT_CASE(Py_mod_state_size, m_size, Py_ssize_t)
        COPYSLOT_CASE(Py_mod_methods, m_methods, PyMethodDef*)
        COPYSLOT_CASE(Py_mod_state_traverse, m_traverse, traverseproc)
        COPYSLOT_CASE(Py_mod_state_clear, m_clear, inquiry)
        COPYSLOT_CASE(Py_mod_state_free, m_free, freefunc)
        case Py_mod_token:
            // With PyInit_, the PyModuleDef is used as the token.
            if (slot->value != &module_def_and_token) {
                PyErr_SetString(PyExc_SystemError,
                                "Py_mod_token must be set to "
                                "&module_def_and_token");
                goto error;
            }
            break;
        default:
            // The remaining slots become m_slots in the def.
            // (`slot` now points to the "rest" of the original
            //  zero-terminated array.)
            if (copying_slots) {
                module_def_and_token.def_gil.m_slots = slot;
            }
            copying_slots = 0;
            break;
        }
    }
    is_set_up = 1;
    return PyModuleDef_Init((void*)&module_def_and_token);

error:
    memset(&module_def_and_token, 0, sizeof(module_def_and_token));
    return NULL;
}
