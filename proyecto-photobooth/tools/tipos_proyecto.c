/* Clase 20 · tipos de ancho fijo y padding en las estructuras del proyecto (espejo en C de las de fotobut/ipc.py).
 * Compilar y correr en la Pi:   gcc -Wall -O2 tools/tipos_proyecto.c -o /tmp/tipos && /tmp/tipos        */
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>

/* Mensaje de control AF_UNIX (64 bytes): vision_gui <-> control_daemon */
struct msg_ctl {
    uint8_t  tipo, flags;
    uint16_t seq, a, b;
    int64_t  ref_ns;
    char     payload[48];
} __attribute__((packed));
struct msg_ctl_natural {                 /* el mismo orden SIN packed: el compilador agrega padding por alineacion */
    uint8_t  tipo, flags;
    uint16_t seq, a, b;
    int64_t  ref_ns;
    char     payload[48];
};

/* Memoria compartida /dev/shm/pb_status */
struct shm_status {
    char     magic[4];
    uint16_t version, flags;
    uint32_t seq;
    uint64_t t_ms;
    uint16_t pot, ldr;
    int16_t  dist;
    uint32_t dist_seq;
    float    temp_c, cpu_c;
    uint16_t ram_used, ram_total;
    char     ip[16];
} __attribute__((packed));
struct shm_status_natural {
    char     magic[4];
    uint16_t version, flags;
    uint32_t seq;
    uint64_t t_ms;
    uint16_t pot, ldr;
    int16_t  dist;
    uint32_t dist_seq;
    float    temp_c, cpu_c;
    uint16_t ram_used, ram_total;
    char     ip[16];
};

int main(void)
{
    printf("== Tamanos de los tipos en esta maquina (aarch64, gcc) ==\n");
    printf("char=%zu short=%zu int=%zu long=%zu long long=%zu void*=%zu float=%zu\n",
           sizeof(char), sizeof(short), sizeof(int), sizeof(long), sizeof(long long), sizeof(void *), sizeof(float));
    printf("uint8_t=%zu uint16_t=%zu uint32_t=%zu uint64_t=%zu int64_t=%zu\n",
           sizeof(uint8_t), sizeof(uint16_t), sizeof(uint32_t), sizeof(uint64_t), sizeof(int64_t));
    printf("\n== struct msg_ctl (socket AF_UNIX) ==\n");
    printf("packed:  sizeof=%zu  (offset ref_ns=%zu, payload=%zu)\n", sizeof(struct msg_ctl),
           offsetof(struct msg_ctl, ref_ns), offsetof(struct msg_ctl, payload));
    printf("natural: sizeof=%zu  (offset ref_ns=%zu, payload=%zu)  -> padding = %zu bytes\n", sizeof(struct msg_ctl_natural),
           offsetof(struct msg_ctl_natural, ref_ns), offsetof(struct msg_ctl_natural, payload),
           sizeof(struct msg_ctl_natural) - sizeof(struct msg_ctl));
    printf("\n== struct shm_status (memoria compartida, 128 bytes reservados) ==\n");
    printf("packed:  sizeof=%zu  (offset seq=%zu, t_ms=%zu, dist=%zu, temp_c=%zu)\n", sizeof(struct shm_status),
           offsetof(struct shm_status, seq), offsetof(struct shm_status, t_ms), offsetof(struct shm_status, dist),
           offsetof(struct shm_status, temp_c));
    printf("natural: sizeof=%zu  (offset t_ms=%zu, temp_c=%zu)  -> padding = %zu bytes\n", sizeof(struct shm_status_natural),
           offsetof(struct shm_status_natural, t_ms), offsetof(struct shm_status_natural, temp_c),
           sizeof(struct shm_status_natural) - sizeof(struct shm_status));
    printf("\n== Pool de fotos (clase 10): 1920x1080x3 bytes uint8 ==\n");
    printf("1 bloque = %u bytes ; 3 bloques = %u bytes (%.2f MiB)\n", 1920u * 1080u * 3u, 3u * 1920u * 1080u * 3u,
           3.0 * 1920 * 1080 * 3 / 1048576.0);
    return 0;
}
