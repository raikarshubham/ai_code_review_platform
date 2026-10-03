// Test fixture for c.yml (C). Never compiled or executed.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/md5.h>

// ruleid: c-hardcoded-secret
const char *password = "hunter2";
// ok: c-hardcoded-secret
const char *username = "admin";

void commands(const char *user) {
    char cmd[256];
    snprintf(cmd, sizeof cmd, "ls %s", user);
    // ruleid: c-command-injection
    system(cmd);
    // ok: c-command-injection
    system("clear");
}

void input(void) {
    char buf[64];
    // ruleid: c-gets
    gets(buf);
    // ruleid: c-unbounded-scanf
    scanf("%s", buf);
    // ok: c-unbounded-scanf
    scanf("%63s", buf);
    // ok: c-gets
    fgets(buf, sizeof buf, stdin);
}

void copy(char *dst, const char *src, const char *name) {
    // ruleid: c-unsafe-string-copy
    strcpy(dst, src);
    // ruleid: c-unsafe-string-copy
    sprintf(dst, "hello %s", name);
    // ok: c-unsafe-string-copy
    snprintf(dst, 64, "hello %s", name);
}

void logs(const char *msg) {
    // ruleid: c-format-string
    printf(msg);
    // ok: c-format-string
    printf("%s", msg);
    // ok: c-format-string
    printf("done\n");
}

void hashes(const unsigned char *data, size_t n, unsigned char *out) {
    // ruleid: c-weak-hash
    MD5(data, n, out);
}
