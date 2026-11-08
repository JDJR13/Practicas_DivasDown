/* panel.c - Practica 7, reto final.
 *
 * Panel con el circuito de las practicas 2 y 3, SIN libgpiod: los LEDs y los
 * botones se manejan escribiendo y leyendo los registros del GPIO a traves de
 * /dev/gpiomem (gpio_regs.h).
 *
 *   Potenciometro (SPI)  -> barra de 0 a 4 LEDs (tramos de 205)
 *   GPIO5                -> alterna barra activa / barra congelada
 *   GPIO6                -> imprime la temperatura del BMP280 y el potenciometro
 *   Ctrl+C               -> apaga LEDs, pines de LED a entrada, termina
 *
 * Los pines 2, 3, 8, 9, 10 y 11 (I2C y SPI) solo se LEEN: se muestra su funcion
 * al iniciar y se avisa al terminar si alguno cambio.
 *
 * Uso: ./panel [direccion_i2c_en_hex]   (si se omite, prueba 0x76 y luego 0x77)
 * Compilar: make panel
 */
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <linux/spi/spidev.h>
#include "gpio_regs.h"

#define N_LEDS       4
#define BOTON_BARRA  5
#define BOTON_TEMP   6
#define TRAMO        205u       /* 1024 / 5, aprox. */
#define PERIODO_US   10000u     /* se muestrea cada 10 ms */
#define ESTABLE      3          /* muestras iguales (30 ms) para aceptar un nivel */
#define FUNC_ENTRADA 0u
#define FUNC_SALIDA  1u

static const unsigned leds[N_LEDS] = {17, 27, 22, 23};
static const unsigned pines_bus[6] = {2, 3, 8, 9, 10, 11};
#define LED_MASCARA (BIT(17) | BIT(27) | BIT(22) | BIT(23))

/* Bandera de salida: la escribe el manejador de senal, la lee el ciclo */
static volatile sig_atomic_t salir = 0;

static void al_recibir_senal(int signo)
{
    (void)signo;
    salir = 1;
}

/* ================= GPIO por registros ================= */

/* Unicos pines en los que este programa escribe campos de GPFSEL */
static int pin_permitido(unsigned pin)
{
    return pin == 17 || pin == 27 || pin == 22 || pin == 23 ||
           pin == 5 || pin == 6;
}

static uint32_t funcion_pin(const gpio_regs_t *gpio, unsigned pin)
{
    unsigned reg = pin / 10;
    unsigned desp = (pin % 10) * 3;
    return (gpio->GPFSEL[reg] >> desp) & 0x7u;
}

/* Cambia solo el campo de 3 bits del pin: leer, borrar el campo, escribir */
static int configurar(gpio_regs_t *gpio, unsigned pin, uint32_t funcion)
{
    if (!pin_permitido(pin)) {
        fprintf(stderr, "Pin %u no permitido: no se escribe\n", pin);
        return -1;
    }
    unsigned reg = pin / 10;
    unsigned desp = (pin % 10) * 3;
    uint32_t valor = gpio->GPFSEL[reg];
    valor &= ~(0x7u << desp);
    valor |= (funcion & 0x7u) << desp;
    gpio->GPFSEL[reg] = valor;
    return 0;
}

static unsigned nivel_pin(const gpio_regs_t *gpio, unsigned pin)
{
    return (gpio->GPLEV[0] >> pin) & 1u;
}

#define N_BUS 6

static const char *nombre_funcion(uint32_t f)
{
    switch (f) {
    case 0: return "entrada";
    case 1: return "salida";
    case 4: return "ALT0";
    case 5: return "ALT1";
    case 6: return "ALT2";
    case 7: return "ALT3";
    case 3: return "ALT4";
    case 2: return "ALT5";
    default: return "?";
    }
}

/* Solo LEE los campos de los pines de I2C y SPI y los guarda en dst */
static void leer_bus(const gpio_regs_t *gpio, uint32_t dst[N_BUS])
{
    for (size_t i = 0; i < N_BUS; i++)
        dst[i] = funcion_pin(gpio, pines_bus[i]);
}

/* Muestra la funcion de cada pin del bus (GPIO8, el chip select del SPI, el
 * driver del kernel lo maneja por software: aparece como salida, no ALT0) */
static void mostrar_bus(const uint32_t f[N_BUS], const char *momento)
{
    printf("Pines de I2C y SPI (%s):", momento);
    for (size_t i = 0; i < N_BUS; i++)
        printf(" GPIO%u=%s", pines_bus[i], nombre_funcion(f[i]));
    printf("\n");
}

/* Lee de nuevo el bus y avisa si algun pin cambio respecto del inicio.
 * Devuelve cuantos pines cambiaron. No escribe nada. */
static int verificar_bus(const gpio_regs_t *gpio, const uint32_t inicial[N_BUS],
                         const char *momento)
{
    uint32_t actual[N_BUS];
    int cambiados = 0;

    leer_bus(gpio, actual);
    for (size_t i = 0; i < N_BUS; i++) {
        if (actual[i] != inicial[i]) {
            printf("AVISO (%s): GPIO%u cambio de %s a %s\n", momento,
                   pines_bus[i], nombre_funcion(inicial[i]),
                   nombre_funcion(actual[i]));
            cambiados++;
        }
    }
    if (cambiados == 0)
        printf("Pines 2, 3, 8, 9, 10 y 11 sin cambios (%s)\n", momento);
    return cambiados;
}

/* ================= Botones: una pulsacion = un evento ================= */

typedef struct {
    unsigned estable;     /* nivel aceptado (0 o 1) */
    unsigned candidato;   /* nivel de la ultima muestra */
    unsigned cuenta;      /* muestras seguidas iguales al candidato */
} boton_t;

static boton_t boton_iniciar(unsigned nivel)
{
    boton_t b = {nivel, nivel, ESTABLE};
    return b;
}

/* Devuelve 1 una sola vez cuando el nivel estable pasa de 0 a 1.
 * Mantener presionado no genera mas eventos: no hay nuevo flanco. */
static int boton_pulsado(boton_t *b, unsigned nivel)
{
    if (nivel != b->candidato) {
        b->candidato = nivel;
        b->cuenta = 1;
        return 0;
    }
    if (b->cuenta < ESTABLE) {
        b->cuenta++;
        if (b->cuenta == ESTABLE && b->candidato != b->estable) {
            b->estable = b->candidato;
            return b->estable == 1u;
        }
    }
    return 0;
}

/* ================= Barra de LEDs ================= */

static void actualizar_barra(gpio_regs_t *gpio, unsigned valor)
{
    unsigned encendidos = valor / TRAMO;      /* 0 a 4 */
    uint32_t mascara = 0;

    if (encendidos > N_LEDS)
        encendidos = N_LEDS;
    for (unsigned i = 0; i < encendidos; i++)
        mascara |= BIT(leds[i]);

    gpio->GPSET[0] = mascara;                 /* una escritura: encender */
    gpio->GPCLR[0] = LED_MASCARA & ~mascara;  /* una escritura: apagar el resto */
}

/* ================= MCP3008 por SPI ================= */

static int pot_leer(int fd_spi, unsigned canal, unsigned *valor)
{
    uint8_t tx[3] = {0x01, (uint8_t)((8u + canal) << 4), 0x00};
    uint8_t rx[3] = {0, 0, 0};
    struct spi_ioc_transfer tr;

    memset(&tr, 0, sizeof(tr));
    tr.tx_buf = (unsigned long)tx;
    tr.rx_buf = (unsigned long)rx;
    tr.len = 3;
    tr.speed_hz = 1000000;
    tr.bits_per_word = 8;
    if (ioctl(fd_spi, SPI_IOC_MESSAGE(1), &tr) < 0)
        return -1;
    *valor = ((unsigned)(rx[1] & 0x03u) << 8) | rx[2];
    return 0;
}

/* ================= BMP280 por I2C ================= */

#define BMP_REG_CALIB 0x88
#define BMP_REG_CTRL  0xF4
#define BMP_REG_TEMP  0xFA

struct bmp_calib {
    uint16_t T1;
    int16_t  T2;
    int16_t  T3;
};

static uint16_t leer_u16_le(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

/* Registro + lectura en una sola transaccion (repeated START) */
static int bmp_leer_registros(int fd, uint16_t addr, uint8_t reg,
                              uint8_t *dst, size_t n)
{
    struct i2c_msg msgs[2];
    struct i2c_rdwr_ioctl_data datos;

    memset(msgs, 0, sizeof(msgs));
    msgs[0].addr = addr;
    msgs[0].flags = 0;
    msgs[0].len = 1;
    msgs[0].buf = &reg;
    msgs[1].addr = addr;
    msgs[1].flags = I2C_M_RD;
    msgs[1].len = (uint16_t)n;
    msgs[1].buf = dst;
    datos.msgs = msgs;
    datos.nmsgs = 2;
    return ioctl(fd, I2C_RDWR, &datos) < 0 ? -1 : 0;
}

/* Coeficientes de calibracion leidos del propio sensor (registros 0x88 a 0x8D) */
static int bmp_calibracion(int fd, uint16_t addr, struct bmp_calib *c)
{
    uint8_t b[6];

    if (bmp_leer_registros(fd, addr, BMP_REG_CALIB, b, sizeof(b)) < 0)
        return -1;
    c->T1 = leer_u16_le(&b[0]);
    c->T2 = (int16_t)leer_u16_le(&b[2]);
    c->T3 = (int16_t)leer_u16_le(&b[4]);
    return 0;
}

static int32_t bmp_temperatura_cruda(const uint8_t r[3])
{
    return (int32_t)(((uint32_t)r[0] << 12) |
                     ((uint32_t)r[1] << 4) |
                     ((uint32_t)r[2] >> 4));
}

/* Compensacion entera del datasheet: devuelve centesimas de grado Celsius */
static int32_t bmp_compensar(const struct bmp_calib *c, int32_t adc_T)
{
    int32_t var1 = (((adc_T >> 3) - ((int32_t)c->T1 << 1)) *
                    (int32_t)c->T2) >> 11;
    int32_t var2 = ((((adc_T >> 4) - (int32_t)c->T1) *
                     ((adc_T >> 4) - (int32_t)c->T1)) >> 12) *
                   (int32_t)c->T3 >> 14;
    return ((var1 + var2) * 5 + 128) >> 8;
}

static int bmp_iniciar(int fd)
{
    /* ctrl_meas: sobremuestreo de temperatura x1, presion x1, modo normal */
    uint8_t cmd[2] = {BMP_REG_CTRL, 0x27};
    return write(fd, cmd, 2) == 2 ? 0 : -1;
}

static int bmp_temperatura(int fd, uint16_t addr, const struct bmp_calib *c,
                           int32_t *centesimas)
{
    uint8_t t[3];

    if (bmp_leer_registros(fd, addr, BMP_REG_TEMP, t, sizeof(t)) < 0)
        return -1;
    *centesimas = bmp_compensar(c, bmp_temperatura_cruda(t));
    return 0;
}

/* ================= Programa principal ================= */

int main(int argc, char *argv[])
{
    int fd_i2c = open("/dev/i2c-1", O_RDWR);
    int fd_spi = open("/dev/spidev0.0", O_RDWR);
    struct bmp_calib calib;
    int direccion = -1;

    if (fd_i2c < 0 || fd_spi < 0) {
        perror("open i2c/spi");
        return 1;
    }

    /* SPI */
    uint8_t modo = SPI_MODE_0;
    ioctl(fd_spi, SPI_IOC_WR_MODE, &modo);

    /* I2C: direccion dada por el usuario o autodeteccion 0x76 / 0x77 */
    int candidatas[2] = {0x76, 0x77};
    int n_cand = 2;
    if (argc > 1) {
        candidatas[0] = (int)strtol(argv[1], NULL, 16);
        n_cand = 1;
    }
    for (int i = 0; i < n_cand; i++) {
        if (ioctl(fd_i2c, I2C_SLAVE, candidatas[i]) < 0)
            continue;
        if (bmp_calibracion(fd_i2c, (uint16_t)candidatas[i], &calib) == 0 &&
            bmp_iniciar(fd_i2c) == 0) {
            direccion = candidatas[i];
            break;
        }
    }
    if (direccion < 0) {
        fprintf(stderr, "No responde el BMP280 (revisa i2cdetect -y 1)\n");
        return 1;
    }
    printf("BMP280 en 0x%02X: dig_T1 = %u, dig_T2 = %d, dig_T3 = %d\n",
           direccion, calib.T1, calib.T2, calib.T3);
    usleep(50000);

    /* GPIO */
    gpio_regs_t *gpio = gpio_abrir();
    if (gpio == NULL)
        return 1;

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = al_recibir_senal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    uint32_t bus_inicial[N_BUS];
    leer_bus(gpio, bus_inicial);
    mostrar_bus(bus_inicial, "al iniciar");

    for (int i = 0; i < N_LEDS; i++)
        configurar(gpio, leds[i], FUNC_SALIDA);
    configurar(gpio, BOTON_BARRA, FUNC_ENTRADA);
    configurar(gpio, BOTON_TEMP, FUNC_ENTRADA);
    gpio->GPCLR[0] = LED_MASCARA;

    boton_t b_barra = boton_iniciar(nivel_pin(gpio, BOTON_BARRA));
    boton_t b_temp = boton_iniciar(nivel_pin(gpio, BOTON_TEMP));
    int congelada = 0;
    unsigned valor = 0;

    printf("Panel listo. GPIO%d: congelar/reanudar barra, GPIO%d: temperatura, "
           "Ctrl+C: salir\n", BOTON_BARRA, BOTON_TEMP);

    while (!salir) {
        if (pot_leer(fd_spi, 0, &valor) < 0) {
            perror("lectura SPI");
            break;
        }

        if (boton_pulsado(&b_barra, nivel_pin(gpio, BOTON_BARRA))) {
            congelada = !congelada;
            printf("Barra %s\n", congelada ? "congelada" : "activa");
            fflush(stdout);
        }

        if (boton_pulsado(&b_temp, nivel_pin(gpio, BOTON_TEMP))) {
            int32_t cent = 0;
            if (bmp_temperatura(fd_i2c, (uint16_t)direccion, &calib, &cent) < 0) {
                perror("lectura BMP280");
            } else {
                printf("Temperatura: %s%d.%02d C | potenciometro: %u\n",
                       cent < 0 ? "-" : "", abs(cent) / 100, abs(cent) % 100,
                       valor);
                fflush(stdout);
            }
        }

        if (!congelada)
            actualizar_barra(gpio, valor);

        usleep(PERIODO_US);
    }

    /* Limpieza: LEDs apagados y sus pines de vuelta a entrada */
    gpio->GPCLR[0] = LED_MASCARA;
    for (int i = 0; i < N_LEDS; i++)
        configurar(gpio, leds[i], FUNC_ENTRADA);
    verificar_bus(gpio, bus_inicial, "al terminar");
    printf("Panel terminado: LEDs apagados\n");

    close(fd_i2c);
    close(fd_spi);
    return 0;
}
