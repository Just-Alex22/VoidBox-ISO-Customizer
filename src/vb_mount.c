#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <linux/limits.h>

static const char *BIND_SRCS[] = {
    "/dev",
    "/dev/pts",
    "/proc",
    "/sys",
    "/run",
    NULL
};

static int
ensure_dir(const char *path)
{
    struct stat st;
    if (stat(path, &st) == 0) return 0;          
    if (mkdir(path, 0755) < 0 && errno != EEXIST) return -1;
    return 0;
}

static PyObject *
vb_bind(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *src = NULL, *dst = NULL;
    if (!PyArg_ParseTuple(args, "ss", &src, &dst))
        return NULL;

    if (ensure_dir(dst) < 0) {
        PyErr_Format(PyExc_OSError,
                     "could not create mountpoint %s: %s", dst, strerror(errno));
        return NULL;
    }

    if (mount(src, dst, NULL, MS_BIND | MS_REC, NULL) < 0) {
        PyErr_Format(PyExc_OSError,
                     "bind mount %s -> %s failed: %s", src, dst, strerror(errno));
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyObject *
vb_umount(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *dst = NULL;
    if (!PyArg_ParseTuple(args, "s", &dst))
        return NULL;

    if (umount2(dst, MNT_DETACH) < 0) {
        
        if (errno != EINVAL && errno != ENOENT) {
            PyErr_Format(PyExc_OSError,
                         "umount %s failed: %s", dst, strerror(errno));
            return NULL;
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
vb_umount_all(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *rootfs = NULL;
    if (!PyArg_ParseTuple(args, "s", &rootfs))
        return NULL;

    
    int n = 0;
    while (BIND_SRCS[n]) n++;

    
    for (int i = n - 1; i >= 0; i--) {
        char dst[PATH_MAX];
        snprintf(dst, sizeof(dst), "%s%s", rootfs, BIND_SRCS[i]);
        umount2(dst, MNT_DETACH);   
    }

    Py_RETURN_NONE;
}

static PyObject *
vb_bind_all(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *rootfs = NULL;
    if (!PyArg_ParseTuple(args, "s", &rootfs))
        return NULL;

    for (int i = 0; BIND_SRCS[i]; i++) {
        char dst[PATH_MAX];
        snprintf(dst, sizeof(dst), "%s%s", rootfs, BIND_SRCS[i]);

        if (ensure_dir(dst) < 0) {
            PyErr_Format(PyExc_OSError,
                         "could not create %s: %s", dst, strerror(errno));
            return NULL;
        }

        if (mount(BIND_SRCS[i], dst, NULL, MS_BIND | MS_REC, NULL) < 0) {
            PyErr_Format(PyExc_OSError,
                         "bind mount %s -> %s failed: %s",
                         BIND_SRCS[i], dst, strerror(errno));
            return NULL;
        }
    }

    Py_RETURN_NONE;
}

static PyMethodDef vb_mount_methods[] = {
    { "bind",       vb_bind,       METH_VARARGS,
      "bind(src, dst)\nBind-mount src onto dst." },
    { "umount",     vb_umount,     METH_VARARGS,
      "umount(dst)\nLazy unmount dst." },
    { "umount_all", vb_umount_all, METH_VARARGS,
      "umount_all(rootfs)\nUnmount all VoidBox bind points from rootfs." },
    { "bind_all",   vb_bind_all,   METH_VARARGS,
      "bind_all(rootfs)\nBind-mount /dev /dev/pts /proc /sys /run into rootfs." },
    { NULL, NULL, 0, NULL }
};

static struct PyModuleDef vb_mount_module = {
    PyModuleDef_HEAD_INIT,
    "vb_mount",
    "VoidBox — native mount/umount wrappers",
    -1,
    vb_mount_methods,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_vb_mount(void)
{
    return PyModule_Create(&vb_mount_module);
}
