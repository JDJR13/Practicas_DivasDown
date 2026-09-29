#include <stdio.h>
#include <pthread.h>
#include <semaphore.h>
#include <unistd.h>

#define TAM_BUFFER 8
#define TOTAL 100

int buffer[TAM_BUFFER];
int in = 0, out = 0;

sem_t espacios_libres;
sem_t elementos_disponibles;
pthread_mutex_t candado = PTHREAD_MUTEX_INITIALIZER;

int producidos = 0, consumidos = 0;

void *productor(void *arg) {
    for (int i = 0; i < TOTAL; i++) {
        usleep(100000); // 100 ms

        sem_wait(&espacios_libres);
        pthread_mutex_lock(&candado);

        buffer[in] = i;
        in = (in + 1) % TAM_BUFFER;
        producidos++;

        pthread_mutex_unlock(&candado);
        sem_post(&elementos_disponibles);
    }
    return NULL;
}

void *consumidor(void *arg) {
    for (int i = 0; i < TOTAL; i++) {
        sem_wait(&elementos_disponibles);
        pthread_mutex_lock(&candado);

        int valor = buffer[out];
        out = (out + 1) % TAM_BUFFER;
        consumidos++;

        pthread_mutex_unlock(&candado);
        sem_post(&espacios_libres);

        printf("Consumido: %d\n", valor);
        usleep(300000); // 300 ms
    }
    return NULL;
}

int main(void) {
    pthread_t hp, hc;

    sem_init(&espacios_libres, 0, TAM_BUFFER);
    sem_init(&elementos_disponibles, 0, 0);

    pthread_create(&hp, NULL, productor, NULL);
    pthread_create(&hc, NULL, consumidor, NULL);

    pthread_join(hp, NULL);
    pthread_join(hc, NULL);

    printf("Total producidos: %d\n", producidos);
    printf("Total consumidos: %d\n", consumidos);

    sem_destroy(&espacios_libres);
    sem_destroy(&elementos_disponibles);
    return 0;
}
