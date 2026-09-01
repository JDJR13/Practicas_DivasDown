#include <stdio.h>
#include <string.h>
#include <sys/utsname.h>

int main() {
    struct utsname info;

    if (uname(&info) != 0) {
        perror("Error al obtener uname");
        return 1;
    }

    printf("=== Reporte del Sistema ===\n");
    printf("Sistema operativo: %s\n", info.sysname);
    printf("Nombre del host:   %s\n", info.nodename);
    printf("Version kernel:    %s\n", info.release);
    printf("Arquitectura:      %s\n", info.machine);

    printf("\n=== CPU ===\n");
    FILE *cpu = fopen("/proc/cpuinfo", "r");
    if (cpu) {
        char line[256];
        while (fgets(line, sizeof(line), cpu)) {
            if (strstr(line, "model name") || strstr(line, "Model") || strstr(line, "Hardware")) {
                printf("%s", line);
            }
        }
        fclose(cpu);
    } else {
        perror("No se pudo abrir /proc/cpuinfo");
    }

    printf("\n=== Memoria ===\n");
    FILE *mem = fopen("/proc/meminfo", "r");
    if (mem) {
        char line[256];
        int count = 0;
        while (fgets(line, sizeof(line), mem) && count < 3) {
            printf("%s", line);
            count++;
        }
        fclose(mem);
    } else {
        perror("No se pudo abrir /proc/meminfo");
    }

    return 0;
}
