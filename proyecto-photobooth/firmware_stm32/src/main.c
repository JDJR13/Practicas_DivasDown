/*
 * SmartBooth FSE - Firmware STM32F103C8T6 (Blue Pill), bare-metal.
 * Mide la distancia con un HC-SR04 y la envia a la Raspberry Pi por UART.
 *
 *   PA0  -> HC-SR04 TRIG   (GPIO salida, pulso de 12 us)
 *   PA1  <- HC-SR04 ECHO   (TIM2_CH2, Input Capture, 1 us de resolucion)
 *                          (ECHO es de 5 V: usar divisor 1k/2k hacia PA1)
 *   PA9  -> USART1_TX      (a GPIO15 / RXD de la Raspberry Pi)
 *   PA10 <- USART1_RX      (desde GPIO14 / TXD de la Raspberry Pi)
 *   PC13 -> LED de la Blue Pill (activo en bajo): parpadea en cada medicion
 *
 * Trama (ASCII, 115200 8N1, 10 Hz):  "DIST:123 cm\r\n"   (medicion valida 2-400 cm)
 *                                    "DIST:ERR\r\n"       (sin eco / fuera de rango)
 *
 * NOTA: en el STM32F103 el pin PA1 pertenece a TIM2_CH2 (TIM1_CH2 esta en PA9,
 * que aqui es USART1_TX), por eso la captura se hace con TIM2.
 */
#include <stdint.h>

#define REG(a) (*(volatile uint32_t *)(a))

/* RCC / FLASH */
#define RCC_CR      REG(0x40021000)
#define RCC_CFGR    REG(0x40021004)
#define RCC_APB2ENR REG(0x40021018)
#define RCC_APB1ENR REG(0x4002101C)
#define FLASH_ACR   REG(0x40022000)
/* GPIO */
#define GPIOA_CRL   REG(0x40010800)
#define GPIOA_CRH   REG(0x40010804)
#define GPIOA_ODR   REG(0x4001080C)
#define GPIOA_BSRR  REG(0x40010810)
#define GPIOC_CRH   REG(0x40011004)
#define GPIOC_BSRR  REG(0x40011010)
/* USART1 */
#define USART1_SR   REG(0x40013800)
#define USART1_DR   REG(0x40013804)
#define USART1_BRR  REG(0x40013808)
#define USART1_CR1  REG(0x4001380C)
/* TIM2 */
#define TIM2_CR1    REG(0x40000000)
#define TIM2_DIER   REG(0x4000000C)
#define TIM2_SR     REG(0x40000010)
#define TIM2_EGR    REG(0x40000014)
#define TIM2_CCMR1  REG(0x40000018)
#define TIM2_CCER   REG(0x40000020)
#define TIM2_CNT    REG(0x40000024)
#define TIM2_PSC    REG(0x40000028)
#define TIM2_ARR    REG(0x4000002C)
#define TIM2_CCR2   REG(0x40000038)
/* NVIC / SysTick */
#define NVIC_ISER0  REG(0xE000E100)
#define SYST_CSR    REG(0xE000E010)
#define SYST_RVR    REG(0xE000E014)
#define SYST_CVR    REG(0xE000E018)

#define TIM2_IRQn       28
#define MEASURE_PERIOD  100u   /* ms -> 10 Hz */
#define ECHO_TIMEOUT    35u    /* ms sin flanco de bajada => sin eco */

enum { ST_IDLE = 0, ST_WAIT_RISE, ST_WAIT_FALL, ST_DONE };
/* [C20-volatile] Estas 4 variables las escribe una ISR (TIM2/SysTick) y las lee main(): sin volatile el compilador las
 * guardaria en un registro y el while de measure_cm() nunca veria el cambio. uint8/16/32 = ancho exacto del Cortex-M3. */
static volatile uint8_t  g_state;
static volatile uint16_t g_t0;
static volatile uint16_t g_width_us;
static volatile uint32_t g_ms;

/* ---------- Interrupciones ---------- */
void SysTick_Handler(void) { g_ms++; }

void TIM2_IRQHandler(void)
{
    uint32_t sr = TIM2_SR;
    if (sr & (1u << 2)) {                    /* CC2IF (bit 2) */
        uint16_t c = (uint16_t)TIM2_CCR2;    /* leer CCR2 limpia CC2IF */
        if (g_state == ST_WAIT_RISE) {
            g_t0 = c;
            TIM2_CCER |= (1u << 5);          /* CC2P=1: ahora flanco de bajada */
            g_state = ST_WAIT_FALL;
        } else if (g_state == ST_WAIT_FALL) {
            g_width_us = (uint16_t)(c - g_t0); /* resta modulo 2^16 */
            TIM2_CCER &= ~(1u << 5);         /* de vuelta a flanco de subida */
            g_state = ST_DONE;
        }
    }
    TIM2_SR = ~((1u << 2) | (1u << 10));     /* limpia CC2IF (bit 2) y CC2OF (bit 10) */
}

/* ---------- Inicializacion ---------- */
static void clock_init(void)
{
    RCC_CR |= (1u << 16);                    /* HSEON */
    while (!(RCC_CR & (1u << 17))) {}        /* HSERDY */
    FLASH_ACR = 0x12;                        /* prefetch + 2 wait states */
    /* PLLSRC=HSE, PLLMUL=x9 (72 MHz), APB1=/2 (36 MHz), APB2=/1 */
    RCC_CFGR = (1u << 16) | (7u << 18) | (4u << 8);
    RCC_CR |= (1u << 24);                    /* PLLON */
    while (!(RCC_CR & (1u << 25))) {}        /* PLLRDY */
    RCC_CFGR |= 2u;                          /* SW = PLL */
    while ((RCC_CFGR & 0xCu) != 0x8u) {}     /* SWS = PLL */
}

static void gpio_init(void)
{
    RCC_APB2ENR |= (1u << 2) | (1u << 4) | (1u << 14); /* GPIOA, GPIOC, USART1 */
    /* PA0 salida PP 2 MHz (TRIG), PA1 entrada pull-down (ECHO) */
    GPIOA_CRL = (GPIOA_CRL & ~0xFFu) | 0x82u;
    GPIOA_ODR &= ~(1u << 1);                 /* pull-down en PA1 */
    GPIOA_BSRR = (1u << 16);                 /* TRIG en bajo */
    /* PA9 AF push-pull 10 MHz (TX), PA10 entrada pull-up (RX) */
    GPIOA_CRH = (GPIOA_CRH & ~0xFF0u) | 0x890u;
    GPIOA_ODR |= (1u << 10);
    /* PC13 salida PP 2 MHz (LED); apagado = alto */
    GPIOC_CRH = (GPIOC_CRH & ~(0xFu << 20)) | (0x2u << 20);
    GPIOC_BSRR = (1u << 13);
}

static void usart1_init(void)
{
    USART1_BRR = 625;                        /* 72 MHz / 115200 */
    USART1_CR1 = (1u << 13) | (1u << 3) | (1u << 2); /* UE | TE | RE */
}

static void tim2_init(void)
{   /* [C21-stm32] Periferico TIM2 CH2 en captura de entrada (PA1): resolucion 1 us, sin driver del SO (bare-metal) */
    RCC_APB1ENR |= 1u;                       /* TIM2EN */
    TIM2_PSC = 71;                           /* 72 MHz / 72 = 1 MHz -> 1 us */
    TIM2_ARR = 0xFFFF;
    TIM2_CCMR1 = (1u << 8) | (3u << 12);     /* CC2S=01 (TI2), filtro IC2F=3 */
    TIM2_CCER = (1u << 4);                   /* CC2E, flanco de subida */
    TIM2_DIER = (1u << 2);                   /* CC2IE (bit 2; el bit 3 es CC3IE) */
    TIM2_EGR = 1u;                           /* UG: carga PSC */
    TIM2_SR = 0;
    NVIC_ISER0 = (1u << TIM2_IRQn);
    TIM2_CR1 = 1u;                           /* CEN */
}

static void systick_init(void)
{
    SYST_RVR = 72000u - 1u;                  /* 1 ms a 72 MHz */
    SYST_CVR = 0;
    SYST_CSR = 7u;                           /* reloj CPU, interrupcion, enable */
}

/* ---------- Utilidades ---------- */
static void delay_us(uint16_t us)
{
    uint16_t t = (uint16_t)TIM2_CNT;
    while ((uint16_t)((uint16_t)TIM2_CNT - t) < us) {}
}

static void uart_putc(char c)
{
    while (!(USART1_SR & (1u << 7))) {}      /* TXE */
    USART1_DR = (uint8_t)c;
}

static void uart_puts(const char *s) { while (*s) uart_putc(*s++); }

static void uart_putu(uint32_t v)
{
    char b[6]; int n = 0;
    do { b[n++] = (char)('0' + v % 10u); v /= 10u; } while (v);
    while (n) uart_putc(b[--n]);
}

/* Devuelve la distancia en cm (2-400) o -1 si no hay eco valido. */
static int measure_cm(void)
{
    g_state = ST_WAIT_RISE;
    GPIOA_BSRR = 1u;                         /* TRIG = 1 */
    delay_us(12);
    GPIOA_BSRR = (1u << 16);                 /* TRIG = 0 */

    uint32_t t_end = g_ms + ECHO_TIMEOUT;
    while (g_state != ST_DONE && (int32_t)(g_ms - t_end) < 0) {}

    if (g_state != ST_DONE) {                /* timeout: restaurar captura */
        TIM2_CCER &= ~(1u << 5);
        g_state = ST_IDLE;
        return -1;
    }
    g_state = ST_IDLE;
    uint32_t cm = g_width_us / 58u;          /* 58 us de eco = 1 cm */
    if (cm < 2u || cm > 400u) return -1;
    return (int)cm;
}

int main(void)
{
    clock_init();
    gpio_init();
    usart1_init();
    tim2_init();
    systick_init();

    uint32_t next = g_ms + MEASURE_PERIOD;
    uint32_t led = 0;
    for (;;) {
        while ((int32_t)(g_ms - next) < 0) {}
        next += MEASURE_PERIOD;

        int cm = measure_cm();
        if (cm < 0) uart_puts("DIST:ERR\r\n");
        else { uart_puts("DIST:"); uart_putu((uint32_t)cm); uart_puts(" cm\r\n"); }

        led ^= 1u;                           /* parpadeo del LED (activo en bajo) */
        GPIOC_BSRR = led ? (1u << 29) : (1u << 13);
    }
}
