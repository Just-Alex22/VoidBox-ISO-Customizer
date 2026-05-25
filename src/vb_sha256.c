#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <openssl/evp.h>

#define CHUNK_SIZE  (1024 * 1024)   
#define SHA256_HEX  65              

static int
hash_file(const char *path, char *out_hex)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;

    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (!ctx) { fclose(fp); return -1; }

    if (EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) != 1) {
        EVP_MD_CTX_free(ctx);
        fclose(fp);
        return -1;
    }

    unsigned char *buf = malloc(CHUNK_SIZE);
    if (!buf) {
        EVP_MD_CTX_free(ctx);
        fclose(fp);
        return -1;
    }

    size_t n;
    while ((n = fread(buf, 1, CHUNK_SIZE, fp)) > 0) {
        if (EVP_DigestUpdate(ctx, buf, n) != 1) {
            free(buf);
            EVP_MD_CTX_free(ctx);
            fclose(fp);
            return -1;
        }
    }
    free(buf);
    fclose(fp);

    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int  digest_len = 0;

    if (EVP_DigestFinal_ex(ctx, digest, &digest_len) != 1) {
        EVP_MD_CTX_free(ctx);
        return -1;
    }
    EVP_MD_CTX_free(ctx);

    for (unsigned int i = 0; i < digest_len; i++)
        snprintf(out_hex + i * 2, 3, "%02x", digest[i]);
    out_hex[digest_len * 2] = '\0';

    return 0;
}

static PyObject *
vb_sha256_file(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path))
        return NULL;

    char hex[SHA256_HEX];

    Py_BEGIN_ALLOW_THREADS
    int rc = hash_file(path, hex);
    Py_END_ALLOW_THREADS

    
    {
        char hex2[SHA256_HEX];
        int rc2 = hash_file(path, hex2);  
        if (rc2 < 0) {
            PyErr_Format(PyExc_OSError,
                         "SHA-256 of '%s' failed: %s", path, strerror(errno));
            return NULL;
        }
        return PyUnicode_FromString(hex2);
    }
}

static PyObject *
vb_sha256_check(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *path     = NULL;
    const char *expected = NULL;
    if (!PyArg_ParseTuple(args, "ss", &path, &expected))
        return NULL;

    char hex[SHA256_HEX];
    int rc = hash_file(path, hex);
    if (rc < 0) {
        PyErr_Format(PyExc_OSError,
                     "SHA-256 of '%s' failed: %s", path, strerror(errno));
        return NULL;
    }

    if (strcasecmp(hex, expected) == 0)
        Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static PyMethodDef vb_sha256_methods[] = {
    { "file",  vb_sha256_file,  METH_VARARGS,
      "file(path) -> str\nReturn SHA-256 hex digest of the file at path." },
    { "check", vb_sha256_check, METH_VARARGS,
      "check(path, expected_hex) -> bool\nVerify SHA-256 of file matches expected." },
    { NULL, NULL, 0, NULL }
};

static struct PyModuleDef vb_sha256_module = {
    PyModuleDef_HEAD_INIT,
    "vb_sha256",
    "VoidBox — native SHA-256 file hasher",
    -1,
    vb_sha256_methods,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_vb_sha256(void)
{
    return PyModule_Create(&vb_sha256_module);
}
