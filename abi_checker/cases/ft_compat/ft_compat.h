
/* "PyInit_" shim for Python extension modules that use the PyModExport_* hook
 * (as proposed in PEP 793).
 *
 * In *one* C file (the one that defines the PyModExport_* hook):
 * - define FTCOMPAT_MODNAME to the name of your module
 * - include "ft_compat.h" (after <Python.h>)
 *
 * There are some limitations on the slots array:
 * - Slots added in PEP 793 (name, doc, methods, state_*, token) must come
 *   before any other slots.
 * - Py_mod_token, if used, must be set to `&ftcompat_token` (which is defined
 *   in this header).
 *
 * Note that the shim will call your PyModExport_* hook with NULL as the "spec"
 * argument.
 *
 * The shim should be ABI-compatible with Python 3.5 to 3.14 and free-threaded
 * builds of 3.13 & 3.14, *if* compiled with opaque PyObject structs (to
 * ensure that, for example, `Py_INCREF` calls an ABI function rather than
 * access a PyObject member).
 */

#include <string.h>     // for memset

#ifndef PyMODINIT_FUNC
#error "This header must be included after Python.h"
#endif

#ifndef Py_LIMITED_API
#error "This header requires Py_LIMITED_API"
#endif

#ifndef FTCOMPAT_MODNAME
#error "Define FTCOMPAT_MODNAME to the name of the extension before including this header"
#endif

/* Define some PEP 793 API for Python versions that don't have it */

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

/* Shim structs, mirroring the stable ABI ("gil") and the
 * 3.14 free-threaded ABI ("ft")
 */

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

/* Union to reserve space for both variants of the PyModuleDef shim */

union ftcompat_PyModuleDef {
    struct ftcompat_gil_PyModuleDef def_gil;
    struct ftcompat_ft_PyModuleDef def_ft;
};

/* Helper to construct name using the user's extension module name */

#define FTCOMPAT_APPEND_MODNAME3(P, M) P ## M
#define FTCOMPAT_APPEND_MODNAME2(P, M) FTCOMPAT_APPEND_MODNAME3(P, M)
#define FTCOMPAT_APPEND_MODNAME(PREFIX) \
    FTCOMPAT_APPEND_MODNAME2(PREFIX, FTCOMPAT_MODNAME)

/* Forward definitions */

PyMODEXPORT_FUNC FTCOMPAT_APPEND_MODNAME(PyModExport_)(PyObject *);
PyMODINIT_FUNC FTCOMPAT_APPEND_MODNAME(PyInit_)(void);

/* Static PyModuleDef (and token) */

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

    // Check the version (sadly, Py_Version is quite new)

    PyObject *hexversion_obj = PySys_GetObject("hexversion");  // borrowed ref
    if (!hexversion_obj) {
        PyErr_SetString(PyExc_ImportError, "sys.hexversion not found");
        return NULL;
    }
    long hexversion = PyLong_AsLong(hexversion_obj);
    if (hexversion < 0 && PyErr_Occurred()) {
        return NULL;
    }
    if (hexversion > 0x030f0000) {
        PyErr_SetString(PyExc_ImportError, "PyInit_* used on Python 3.15+");
        return NULL;
    }

    // Determine if we have free-threaded ABI

    PyObject *obj_size_obj = PyObject_CallMethod(Py_None, "__sizeof__", "");
    if (!obj_size_obj) {
        return NULL;
    }
    Py_ssize_t obj_size = PyLong_AsSsize_t(obj_size_obj);
    Py_DECREF(obj_size_obj);

    int freethreading_abi;
    if (obj_size == (Py_ssize_t)sizeof(struct ftcompat_gil_PyObject)) {
        freethreading_abi = 0;
    }
    else if (obj_size == (Py_ssize_t)sizeof(struct ftcompat_ft_PyObject)) {
        freethreading_abi = 1;
    }
    else {
         if (!PyErr_Occurred()) {
            PyErr_SetString(PyExc_ImportError, "Onknown object size");
         }
         return NULL;
    }

    // One more safety check

    if (freethreading_abi && hexversion < 0x030d0000) {
        PyErr_SetString(PyExc_ImportError, "'t' ABI found below Python 3.13");
        return NULL;
    }

    // Call the new export hook and construct a moduledef shim from it

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
            if (!copying_slots) {
                PyErr_SetString(PyExc_SystemError,
                                "Py_mod_token must be specified earlier");
                goto error;
            }
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
