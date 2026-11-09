/* Tabla de vectores y Reset_Handler minimos para STM32F103 (Cortex-M3). */
#include <stdint.h>

extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
int main(void);
void Reset_Handler(void);
void Default_Handler(void) { for (;;) {} }

void NMI_Handler(void)        __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void)  __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void);
void TIM2_IRQHandler(void);

__attribute__((section(".isr_vector"), used))
void (*const g_vectors[])(void) = {
    (void (*)(void))(&_estack),   /* 0  SP inicial */
    Reset_Handler,                /* 1  Reset */
    NMI_Handler,                  /* 2  */
    HardFault_Handler,            /* 3  */
    Default_Handler, Default_Handler, Default_Handler, /* 4-6 */
    0, 0, 0, 0,                   /* 7-10 reservados */
    Default_Handler,              /* 11 SVC */
    Default_Handler,              /* 12 DebugMon */
    0,                            /* 13 reservado */
    Default_Handler,              /* 14 PendSV */
    SysTick_Handler,              /* 15 SysTick */
    /* IRQ0..IRQ27 */
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    Default_Handler, Default_Handler, Default_Handler, Default_Handler,
    TIM2_IRQHandler,              /* IRQ28 TIM2 */
};

void Reset_Handler(void)
{
    uint32_t *src = &_sidata, *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; ) *dst++ = 0;
    main();
    for (;;) {}
}
