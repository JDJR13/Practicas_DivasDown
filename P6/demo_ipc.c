#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

int main(void)
{
    int fd[2];
    char buf[64];
    const char *msg = "hola desde el padre";

    if (pipe(fd) < 0) {
        perror("pipe");
        return 1;
    }

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        // Hijo: lee del pipe
        close(fd[1]);
        ssize_t n = read(fd[0], buf, sizeof(buf) - 1);
        buf[n] = '\0';
        printf("Hijo (pid %d) recibio: %s\n", getpid(), buf);
        close(fd[0]);
        _exit(0);
    } else {
        // Padre: escribe en el pipe
        close(fd[0]);
        write(fd[1], msg, strlen(msg));
        close(fd[1]);
        wait(NULL);
        printf("Padre (pid %d) termino\n", getpid());
    }

    return 0;
}
