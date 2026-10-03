// Test fixture for c.yml (C++). Never compiled or executed.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// ruleid: c-hardcoded-secret
char api_key[] = "sk-live-123456";

class Runner {
public:
    void run(const std::string &user) {
        std::string cmd = "ping " + user;
        // ruleid: c-command-injection
        std::system(cmd.c_str());
        // ruleid: c-command-injection
        system(cmd.c_str());
    }

    void copy(char *dst, const char *src) {
        // ruleid: c-unsafe-string-copy
        strcat(dst, src);
        // ok: c-unsafe-string-copy
        std::string safe = std::string(dst) + src;
    }

    void log(const char *msg) {
        // ruleid: c-format-string
        fprintf(stderr, msg);
        // ok: c-format-string
        fprintf(stderr, "%s", msg);
    }
};
