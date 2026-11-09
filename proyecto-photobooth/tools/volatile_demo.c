/* Clase 20 · volatile: una variable que cambia FUERA del flujo normal (ISR en el STM32, handler de senal aqui).
 * Sin volatile, con -O2, el compilador lee la variable UNA vez y el ciclo nunca termina. */
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

#ifdef CON_VOLATILE
static volatile int g_listo;           /* igual que g_state / g_width_us del firmware del STM32 */
#else
static int g_listo;
#endif

static void handler(int s) { (void)s; g_listo = 1; }

void esperar(void) { while (!g_listo) { } }

int main(void)
{
    signal(SIGALRM, handler);
    alarm(1);                           /* a 1 s llega la senal y pone g_listo = 1 */
    esperar();
    puts("salio del ciclo: el cambio SI se vio");
    return 0;
}
