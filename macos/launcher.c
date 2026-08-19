#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int read_line(const char *path, char *out, size_t cap)
{
    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        return -1;
    }
    if (fgets(out, (int)cap, fp) == NULL) {
        fclose(fp);
        return -1;
    }
    fclose(fp);
    size_t n = strlen(out);
    while (n > 0 && (out[n - 1] == '\n' || out[n - 1] == '\r')) {
        out[--n] = '\0';
    }
    return n == 0 ? -1 : 0;
}

static int resource_path(const char *name, char *out, size_t cap)
{
    char exe[PATH_MAX];
    uint32_t size = sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0) {
        return -1;
    }
    char resolved[PATH_MAX];
    if (realpath(exe, resolved) == NULL) {
        return -1;
    }
    char *macos_dir = dirname(resolved);
    char contents[PATH_MAX];
    snprintf(contents, sizeof(contents), "%s/..", macos_dir);
    char contents_real[PATH_MAX];
    if (realpath(contents, contents_real) == NULL) {
        return -1;
    }
    snprintf(out, cap, "%s/Resources/%s", contents_real, name);
    return 0;
}

int main(int argc, char **argv)
{
    (void)argc;
    char project_file[PATH_MAX];
    char project_root[PATH_MAX];
    char site_file[PATH_MAX];
    char site_path[PATH_MAX];
    char src_path[PATH_MAX];

    if (resource_path("project_root", project_file, sizeof(project_file)) != 0 ||
        read_line(project_file, project_root, sizeof(project_root)) != 0) {
        fprintf(stderr, "AI Translate: missing Resources/project_root\n");
        return 1;
    }
    if (chdir(project_root) != 0) {
        perror("chdir");
        return 1;
    }
    setenv("AI_TRANSLATE_PROJECT_ROOT", project_root, 1);
    setenv("AI_TRANSLATE_HOST_NAME", "AI Translate", 1);
    if (resource_path("site_packages", site_file, sizeof(site_file)) != 0 ||
        read_line(site_file, site_path, sizeof(site_path)) != 0) {
        fprintf(stderr, "AI Translate: missing Resources/site_packages\n");
        return 1;
    }
    snprintf(src_path, sizeof(src_path), "%s/src", project_root);

    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.parse_argv = 0;
    PyStatus status = PyConfig_SetBytesString(&config, &config.program_name, argv[0]);
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        Py_ExitStatusException(status);
    }
    char *py_argv[] = {(char *)"AI Translate", (char *)"app"};
    status = PyConfig_SetBytesArgv(&config, 2, py_argv);
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        Py_ExitStatusException(status);
    }
    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        Py_ExitStatusException(status);
    }

    PyObject *sys_path = PySys_GetObject("path");
    PyObject *src = PyUnicode_FromString(src_path);
    PyObject *site = PyUnicode_FromString(site_path);
    if (sys_path == NULL || src == NULL || site == NULL) {
        PyErr_Print();
        Py_Finalize();
        return 1;
    }
    PyList_Insert(sys_path, 0, site);
    PyList_Insert(sys_path, 0, src);
    Py_DECREF(src);
    Py_DECREF(site);

    PyObject *module = PyImport_ImportModule("ai_translate.app");
    if (module == NULL) {
        PyErr_Print();
        Py_Finalize();
        return 1;
    }
    PyObject *fn = PyObject_GetAttrString(module, "main");
    Py_DECREF(module);
    if (fn == NULL) {
        PyErr_Print();
        Py_Finalize();
        return 1;
    }
    PyObject *arg = Py_BuildValue("[s]", "app");
    PyObject *result = PyObject_CallFunctionObjArgs(fn, arg, NULL);
    Py_DECREF(fn);
    Py_XDECREF(arg);
    if (result == NULL) {
        PyErr_Print();
        Py_Finalize();
        return 1;
    }
    int rc = PyLong_Check(result) ? (int)PyLong_AsLong(result) : 0;
    Py_DECREF(result);
    Py_Finalize();
    return rc;
}
