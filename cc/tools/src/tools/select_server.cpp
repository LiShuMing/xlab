/**
 * @file select_server.cpp
 * @author your name (you@domain.com)
 * @brief 
 * @version 0.1
 * @date 2024-11-17
 * 
 * @copyright Copyright (c) 2024
 * 
 * 1. 程序使用了一个数组fd_A，通信开始后把需要通信的多个socket描述符都放入此数组。
 * 2. 首先生成一个叫sock_fd的socket描述符，用于监听端口。
 * 3. 将sock_fd和数组fd_A中不为0的描述符放入select将检查的集合fdsr。
 * 4. 处理fdsr中可以接收数据的连接。如果是sock_fd，表明有新连接加入，将新加入连接的socket描述符放置到fd_A。
*/
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

#define MYPORT 1234
#define BACKLOG 5

#define BUF_SIZE 200

int fd_A[BACKLOG];
int conn_amount;
void showclient() {
    int i;
    printf("client amount : %d\n", conn_amount);
    for (i = 0; i < BACKLOG; i++) printf("[%d]:%d ", i, fd_A[i]);
    printf("\n\n");
}

int main() {
    int sock_fd, new_fd;
    struct sockaddr_in server_addr;
    struct sockaddr_in client_addr;
    socklen_t sin_size;
    int yes = 1;
    char buf[BUF_SIZE];
    int ret;
    int i;

    if ((sock_fd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("socket\n");
        exit(1);
    }

    if (setsockopt(sock_fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(int)) == -1) {
        perror("setsockopt\n");
        exit(1);
    }

    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(MYPORT);
    server_addr.sin_addr.s_addr = INADDR_ANY; //自动转换本地IP
    memset(server_addr.sin_zero, '\0', sizeof(server_addr.sin_zero));

    if (bind(sock_fd, (struct sockaddr*)&server_addr, sizeof(server_addr)) == -1) {
        perror("bind\n");
        exit(1);
    }
    if (listen(sock_fd, BACKLOG) == -1) {
        perror("listen\n");
        exit(1);
    }
    printf("listen port %d\n", MYPORT);

    fd_set fdsr;
    int maxsock;
    struct timeval tv;

    conn_amount = 0;
    sin_size = sizeof(client_addr);
    maxsock = sock_fd;
    while (1) {
        FD_ZERO(&fdsr);
        FD_SET(sock_fd, &fdsr);

        tv.tv_sec = 30;
        tv.tv_usec = 0;

        for (i = 0; i < BACKLOG; i++) {
            if (fd_A[i] != 0) {
                FD_SET(fd_A[i], &fdsr);
            }
        }

        ret = select(maxsock + 1, &fdsr, NULL, NULL, &tv);
        if (ret < 0) {
            perror("select");
            break;
        } else if (ret == 0) {
            printf("timeout\n");
            continue;
        }
        if (FD_ISSET(sock_fd, &fdsr)) {
            new_fd = accept(sock_fd, (struct sockaddr*)&client_addr, &sin_size);
            if (new_fd <= 0) {
                perror("accept");
                continue;
            }

            if (conn_amount < BACKLOG) {
                fd_A[conn_amount++] = new_fd;
                printf("new connection client[%d] %s:%d\n", conn_amount,
                       inet_ntoa(client_addr.sin_addr), ntohs(client_addr.sin_port));
                if (new_fd > maxsock) maxsock = new_fd;
            } else {
                printf("max connections arrive,exit\n");
                send(new_fd, "bye", 4, 0);
                close(new_fd);
                break;
            }
        }
        showclient();
    }

    for (i = 0; i < BACKLOG; i++) {
        if (fd_A[i] != 0) close(fd_A[i]);
    }
    exit(0);
}