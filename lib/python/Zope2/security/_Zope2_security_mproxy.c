/*****************************************************************************
*
* Copyright (c) 2003, 2004 Zope Corporation and Contributors.
* All Rights Reserved.
*
* This software is subject to the provisions of the Zope Public License,
* Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
* THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
* WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
* FOR A PARTICULAR PURPOSE.
*
******************************************************************************
Security Proxy Implementation

$Id: _proxy.c 26705 2004-07-23 16:22:56Z jim $
*/

#include <Python.h>

static PyTypeObject *_Proxy = NULL;

#define DECLARE_STRING(N) static PyObject *str_##N

typedef struct {
  PyObject_HEAD
  PyObject *proxy_object;
  PyObject *proxy_checker;
} MProxy;

static PyObject *
mproxy_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
  static char *kwlist[] = {"object", "checker", 0};
  MProxy *self;
  PyObject *object;
  PyObject *checker;

  if (!PyArg_ParseTupleAndKeywords(args, kwds,
                                   "OO:_Proxy.__new__", kwlist,
                                   &object, &checker))
    return NULL;

  if (checker == Py_None)
    {
      PyErr_SetString(PyExc_ValueError, "None passed as proxy checker");
      return NULL;
    }

  self = (MProxy *)type->tp_alloc(type, 0);
  if (self == NULL)
    return NULL;
  Py_INCREF(object);
  Py_INCREF(checker);
  self->proxy_object = object;
  self->proxy_checker = checker;
  return (PyObject *)self;
}

static PyObject *
clean_args(MProxy *self, PyObject *args, int l)
{
  PyObject *result;
  int i;

  result = PyTuple_New(l);
  if (result == NULL)
    return NULL;

  for (i=0; i < l; i++)
    {
      PyObject *o;

      o = PyTuple_GET_ITEM(args, i);
      if (o != NULL)
        {
          if (o->ob_type == self->ob_type)
            o = ((MProxy *)o)->proxy_object;
          Py_INCREF(o);
        }
      PyTuple_SET_ITEM(result, i, o);
    }

  return result;
}

static PyObject *
clean_kwds(MProxy *self, PyObject *kwds)
{
  PyObject *result;
  PyObject *k, *o;
  int pos = 0;

  result = PyDict_New();
  if (result == NULL)
    return NULL;

  while (PyDict_Next(kwds, &pos, &k, &o)) 
    {
      if (o->ob_type == self->ob_type)
        o = ((MProxy *)o)->proxy_object;
      if (PyDict_SetItem(result, k, o) < 0)
        {
          Py_DECREF(result);
          return NULL;
        }
    }
  
  return result;
}

static PyObject *
mproxy_call(MProxy *self, PyObject *args, PyObject *kwds)
{
  PyObject *result = NULL;

  if (args != NULL)
    {
      int i, l;

      l = PyTuple_Size(args);
      if (l < 0)
        return NULL;

      Py_INCREF(args);
      for (i=0; i < l; i++)
        {
          PyObject *o;

          o = PyTuple_GET_ITEM(args, i);
          if (o != NULL && o->ob_type == self->ob_type)
            {
              Py_DECREF(args);
              args = clean_args(self, args, l);
              break;
            }
        }
    }
  
  if (kwds != NULL)
    {
      PyObject *k, *o;
      int pos = 0;

      Py_INCREF(kwds);
      while (PyDict_Next(kwds, &pos, &k, &o)) 
        {
          if (o->ob_type == self->ob_type)
            {
              Py_DECREF(kwds);
              kwds = clean_kwds(self, kwds);
              break;
            }
        }
    }

  result = _Proxy->tp_call((PyObject*)self, args, kwds);
  Py_XDECREF(args);
  Py_XDECREF(kwds);

  return result;
}

static char proxy_doc[] = 
"Mild security proxies.\n"
"\n"
"See mproxy.txt.\n"
;

statichere PyTypeObject
MProxyType = {
  PyObject_HEAD_INIT(NULL)
  0,
  "Zope2.security.mproxy.MProxy",
  sizeof(MProxy),
  0,
  0,
  0,					/* tp_print */
  0,					/* tp_getattr */
  0,					/* tp_setattr */
  0,				/* tp_compare */
  0,				/* tp_repr */
  0,			/* tp_as_number */
  0,			/* tp_as_sequence */
  0,			/* tp_as_mapping */
  0,				/* tp_hash */
  (ternaryfunc)mproxy_call,				/* tp_call */
  0,				/* tp_str */
  0,				/* tp_getattro */
  0,				/* tp_setattro */
  0,					/* tp_as_buffer */
  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_CHECKTYPES |
  Py_TPFLAGS_HAVE_GC,		/* tp_flags */
  proxy_doc,				/* tp_doc */
  0,				/* tp_traverse */
  0,					/* tp_clear */
  0,			/* tp_richcompare */
  0,					/* tp_weaklistoffset */
  0,				/* tp_iter */
  0,				/* tp_iternext */
  0,					/* tp_methods */
  0,					/* tp_members */
  0,					/* tp_getset */
  0,					/* tp_base */
  0,					/* tp_dict */
  0,					/* tp_descr_get */
  0,					/* tp_descr_set */
  0,					/* tp_dictoffset */
  0,				/* tp_init */
  0, /*PyType_GenericAlloc,*/		/* tp_alloc */
  mproxy_new,				/* tp_new */
  0, /*_PyObject_GC_Del,*/		/* tp_free */
};

static PyObject *
module_debug(void)
{
  Py_INCREF(Py_None);
  return Py_None;
}

static PyMethodDef
module_functions[] = {
  {"debug", (PyCFunction)module_debug, METH_NOARGS, ""},
  {NULL}
};

static char
module___doc__[] = "Security proxy implementation.";

void
init_Zope2_security_mproxy(void)
{
  PyObject *m;

  m = PyImport_ImportModule("zope.security.proxy");
  if (m == NULL)
    return;

  _Proxy = (PyTypeObject *)PyObject_GetAttrString(m, "Proxy");
  if (_Proxy == NULL)
    return;
  
  
  MProxyType.ob_type = &PyType_Type;
  MProxyType.tp_alloc = PyType_GenericAlloc;
  MProxyType.tp_free = _PyObject_GC_Del;
  MProxyType.tp_base = _Proxy;
  MProxyType.tp_traverse = _Proxy->tp_traverse;
  MProxyType.tp_clear = _Proxy->tp_clear;
  if (PyType_Ready(&MProxyType) < 0)
    return;
  
  m = Py_InitModule3("_Zope2_security_mproxy", 
                     module_functions, module___doc__);
  if (m == NULL)
    return;
  
  Py_INCREF(&MProxyType);
  PyModule_AddObject(m, "MProxy", (PyObject *)&MProxyType);
}
