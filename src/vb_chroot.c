#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <sys/wait.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <pty.h>       

static void
set_cloexec(int fd)
{
    int flags = fcntl(fd, F_GETFD);
    if (flags != -1)
        fcntl(fd, F_SETFD, flags | FD_CLOEXEC);
}

static char **
dict_to_envp(PyObject *dict)
{
    Py_ssize_t n = PyDict_Size(dict);
    char **envp = calloc(n + 1, sizeof(char *));
    if (!envp) return NULL;

    PyObject *key, *val;
    Py_ssize_t pos = 0;
    Py_ssize_t i   = 0;

    while (PyDict_Next(dict, &pos, &key, &val)) {
        const char *k = PyUnicode_AsUTF8(key);
        const char *v = PyUnicode_AsUTF8(val);
        if (!k || !v) {  continue; }
        size_t len = strlen(k) + strlen(v) + 2; 
        envp[i] = malloc(len);
        if (!envp[i]) break;
        snprintf(envp[i], len, "%s=%s", k, v);
        i++;
    }
    envp[i] = NULL;
    return envp;
}

static void
free_envp(char **envp)
{
    if (!envp) return;
    for (int i = 0; envp[i]; i++)
        free(envp[i]);
    free(envp);
}

static PyObject *
vb_spawn(PyObject *Py_UNUSED(self), PyObject *args)
{
    const char *rootfs = NULL;
    PyObject   *env_dict = NULL;

    if (!PyArg_ParseTuple(args, "sO!", &rootfs, &PyDict_Type, &env_dict))
        return NULL;

    
    if (access(rootfs, F_OK) != 0) {
        PyErr_Format(PyExc_FileNotFoundError,
                     "rootfs path does not exist: %s", rootfs);
        return NULL;
    }

    int master_fd, slave_fd;
    struct winsize ws = { .ws_row = 24, .ws_col = 80 };

    if (openpty(&master_fd, &slave_fd, NULL, NULL, &ws) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    set_cloexec(master_fd);

    char **envp = dict_to_envp(env_dict);
    if (!envp) {
        close(master_fd);
        close(slave_fd);
        PyErr_NoMemory();
        return NULL;
    }

    pid_t pid = fork();

    if (pid < 0) {
        
        close(master_fd);
        close(slave_fd);
        free_envp(envp);
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    if (pid == 0) {
        
        close(master_fd);

        
        if (setsid() < 0) _exit(1);
        if (ioctl(slave_fd, TIOCSCTTY, 0) < 0) _exit(1);

        
        dup2(slave_fd, STDIN_FILENO);
        dup2(slave_fd, STDOUT_FILENO);
        dup2(slave_fd, STDERR_FILENO);
        if (slave_fd > STDERR_FILENO) close(slave_fd);

        
        if (chroot(rootfs) < 0) {
            fprintf(stderr, "[vb_chroot] chroot(%s) failed: %s\n",
                    rootfs, strerror(errno));
            _exit(1);
        }
        if (chdir("/") < 0) _exit(1);

        
        char *argv[] = { "/bin/bash", "--login", NULL };
        execve("/bin/bash", argv, envp);

        
        fprintf(stderr, "[vb_chroot] execve failed: %s\n", strerror(errno));
        _exit(1);
    }

    
    close(slave_fd);
    free_envp(envp);

    
    int flags = fcntl(master_fd, F_GETFL);
    fcntl(master_fd, F_SETFL, flags | O_NONBLOCK);

    return Py_BuildValue("(ii)", master_fd, (int)pid);
}

static PyObject *
vb_reap(PyObject *Py_UNUSED(self), PyObject *args)
{
    int pid;
    if (!PyArg_ParseTuple(args, "i", &pid))
        return NULL;

    int status = 0;
    pid_t ret = waitpid((pid_t)pid, &status, WNOHANG);

    if (ret < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    int exit_code = -1;
    if (ret > 0) {
        if (WIFEXITED(status))
            exit_code = WEXITSTATUS(status);
        else if (WIFSIGNALED(status))
            exit_code = -WTERMSIG(status);
    }

    return PyLong_FromLong(exit_code);
}

static PyObject *
vb_resize_pty(PyObject *Py_UNUSED(self), PyObject *args)
{
    int fd, rows, cols;
    if (!PyArg_ParseTuple(args, "iii", &fd, &rows, &cols))
        return NULL;

    struct winsize ws = { .ws_row = (unsigned short)rows,
                          .ws_col = (unsigned short)cols };
    if (ioctl(fd, TIOCSWINSZ, &ws) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyMethodDef vb_chroot_methods[] = {
    { "spawn",      vb_spawn,      METH_VARARGS,
      "spawn(rootfs, env_dict) -> (master_fd, child_pid)\n"
      "Fork a bash session inside a chroot with a PTY." },
    { "reap",       vb_reap,       METH_VARARGS,
      "reap(child_pid) -> exit_code\n"
      "Non-blocking waitpid. Returns -1 if child still running." },
    { "resize_pty", vb_resize_pty, METH_VARARGS,
      "resize_pty(master_fd, rows, cols)\n"
      "Send TIOCSWINSZ to the PTY master." },
    { NULL, NULL, 0, NULL }
};

static struct PyModuleDef vb_chroot_module = {
    PyModuleDef_HEAD_INIT,
    "vb_chroot",
    "VoidBox — native PTY/chroot spawner",
    -1,
    vb_chroot_methods,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_vb_chroot(void)
{
    return PyModule_Create(&vb_chroot_module);
}
