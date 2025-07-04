#include <string.h>     // memset

#ifndef PyMODINIT_FUNC
#error "This header must pe included after Python.h"
#endif

#ifndef Py_LIMITED_API
#error "This header requires Py_LIMITED_API"
#endif

#ifndef FTCOMPAT_MODNAME
#error "define FTCOMPAT_MODNAME before including this header"
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
#endif
#ifndef PyMODEXPORT_FUNC
#define PyMODEXPORT_FUNC Py_EXPORTED_SYMBOL PyModuleDef_Slot*
#endif

struct ftcompat_gil_PyObject {
    alignas(Py_ssize_t) alignas(4) Py_ssize_t ob_refcnt;
    PyTypeObject *ob_type;
};

struct ftcompat_ft_PyObject {
    alignas(uintptr_t) alignas(4) uintptr_t ob_tid;
    uint16_t ob_flags;
    char /* PyMutex */ ob_mutex;
    uint8_t ob_gc_bits;
    uint32_t ob_ref_local;
    Py_ssize_t ob_ref_shared;
    PyTypeObject *ob_type;
};

struct ftcompat_gil_PyModuleDef_Base {
    struct ftcompat_gil_PyObject ob_base;
    PyObject* (*m_init)(void);
    Py_ssize_t m_index;
    PyObject* m_copy;
};

struct ftcompat_ft_PyModuleDef_Base {
    struct ftcompat_ft_PyObject ob_base;
    PyObject* (*m_init)(void);
    Py_ssize_t m_index;
    PyObject* m_copy;
};

struct ftcompat_gil_PyModuleDef {
    struct ftcompat_gil_PyModuleDef_Base m_base;
    const char* m_name;
    const char* m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    PyModuleDef_Slot *m_slots;
    traverseproc m_traverse;
    inquiry m_clear;
    freefunc m_free;
};

struct ftcompat_ft_PyModuleDef {
    struct ftcompat_ft_PyModuleDef_Base m_base;
    const char* m_name;
    const char* m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    PyModuleDef_Slot *m_slots;
    traverseproc m_traverse;
    inquiry m_clear;
    freefunc m_free;
};

union ftcompat_PyModuleDef {
    struct ftcompat_gil_PyModuleDef def_gil;
    struct ftcompat_ft_PyModuleDef def_ft;
};

#define FTCOMPAT_APPEND_MODNAME3(P, M) P ## M
#define FTCOMPAT_APPEND_MODNAME2(P, M) FTCOMPAT_APPEND_MODNAME3(P, M)
#define FTCOMPAT_APPEND_MODNAME(PREFIX) \
    FTCOMPAT_APPEND_MODNAME2(PREFIX, FTCOMPAT_MODNAME)

PyMODEXPORT_FUNC FTCOMPAT_APPEND_MODNAME(PyModExport_)(PyObject *);

PyMODINIT_FUNC FTCOMPAT_APPEND_MODNAME(PyInit_)(void);

static union ftcompat_PyModuleDef ftcompat_token;

PyMODINIT_FUNC
FTCOMPAT_APPEND_MODNAME(PyInit_)(void)
{
    static int is_set_up;
    if (is_set_up) {
        // Take care to only set up the static PyModuleDef once.
        // (PyModExport might theoretically return different data each time.)
        return PyModuleDef_Init((void*)&ftcompat_token);
    }

    PyObject *abiflags_str = PySys_GetObject("abiflags");  // borrowed ref
    if (!abiflags_str) {
        PyErr_SetString(PyExc_ImportError, "sys.abiflags not found");
        return NULL;
    }
    PyObject *abiflags_bytes = PyUnicode_AsUTF8String(abiflags_str);
    if (!abiflags_bytes) {
        return NULL;
    }
    const char *abiflags = PyBytes_AsString(abiflags_bytes);
    if (!abiflags) {
        return NULL;
    }
    Py_DECREF(abiflags_bytes);

    int freethreading_abi = strchr(abiflags, 't') != NULL;


    PyObject *hexversion_obj = PySys_GetObject("hexversion");  // borrowed ref
    if (!abiflags_str) {
        PyErr_SetString(PyExc_ImportError, "sys.hexversion not found");
        return NULL;
    }
    long hexversion = PyLong_AsLong(hexversion_obj);
    if (hexversion < 0 && PyErr_Occurred()) {
        return NULL;
    }
    if (freethreading_abi && hexversion < 0x030d0000) {
        PyErr_SetString(PyExc_ImportError, "'t' ABI found below Python 3.13");
        return NULL;
    }
    if (hexversion > 0x030f0000) {
        PyErr_SetString(PyExc_ImportError, "PyInit_* used on Python 3.15+");
        return NULL;
    }

    PyModuleDef_Slot *slot = FTCOMPAT_APPEND_MODNAME(PyModExport_)(NULL);

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
                if (freethreading_abi) {                                    \
                    ftcompat_token.def_ft.MEMBER = (TYPE)(slot->value);     \
                } else {                                                    \
                    ftcompat_token.def_gil.MEMBER = (TYPE)(slot->value);    \
                }                                                           \
                break;                                                      \
            /////////////////////////////////////////////////////////////////
        COPYSLOT_CASE(Py_mod_name, m_name, char*)
        COPYSLOT_CASE(Py_mod_doc, m_doc, char*)
        COPYSLOT_CASE(Py_mod_state_size, m_size, Py_ssize_t)
        COPYSLOT_CASE(Py_mod_methods, m_methods, PyMethodDef*)
        COPYSLOT_CASE(Py_mod_state_traverse, m_traverse, traverseproc)
        COPYSLOT_CASE(Py_mod_state_clear, m_clear, inquiry)
        COPYSLOT_CASE(Py_mod_state_free, m_free, freefunc)
#       undef COPYSLOT_CASE
        case Py_mod_token:
            // With PyInit_, the PyModuleDef is used as the token.
            if (slot->value != &ftcompat_token) {
                PyErr_SetString(PyExc_SystemError,
                                "Py_mod_token must be set to "
                                "&ftcompat_token");
                goto error;
            }
            break;
        default:
            // The remaining slots become m_slots in the def.
            // (`slot` now points to the "rest" of the original
            //  zero-terminated array.)
            if (copying_slots) {
                if (freethreading_abi) {
                    ftcompat_token.def_ft.m_slots = slot;
                } else {
                    ftcompat_token.def_gil.m_slots = slot;
                }
            }
            copying_slots = 0;
            break;
        }
    }
    is_set_up = 1;
    return PyModuleDef_Init((void*)&ftcompat_token);

error:
    memset(&ftcompat_token, 0, sizeof(ftcompat_token));
    return NULL;
}
#undef FTCOMPAT_APPEND_MODNAME
#undef FTCOMPAT_APPEND_MODNAME2
#undef FTCOMPAT_APPEND_MODNAME3
