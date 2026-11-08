#ifndef CENTINELA_LOGICA_H
#define CENTINELA_LOGICA_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include "centinela_cfg.h"

static int32_t temp_base(const int32_t *lecturas, size_t n)
{
	int64_t suma = 0;

	if (lecturas == NULL || n == 0)
		return 0;
	for (size_t i = 0; i < n; i++)
		suma += lecturas[i];
	return (int32_t)(suma / (int64_t)n);
}

static int32_t umbral_desde_pot(int32_t base_c100, unsigned pot)
{
	int32_t parte_pot = (int32_t)(((int64_t)pot * UMBRAL_RANGO_C100) / 1023);

	return base_c100 + UMBRAL_MIN_C100 + parte_pot;
}

static unsigned nivel_barra(int32_t margen_c100)
{
	if (margen_c100 <= 0)
		return 4;
	if (margen_c100 <= 100)
		return 3;
	if (margen_c100 <= 200)
		return 2;
	if (margen_c100 <= 400)
		return 1;
	return 0;
}

static uint32_t mascara_leds(unsigned nivel)
{
	static const uint32_t leds[4] = { BIT(LED_1), BIT(LED_2), BIT(LED_3), BIT(LED_4) };
	uint32_t mascara = 0;

	if (nivel > 4)
		nivel = 4;
	for (unsigned i = 0; i < nivel; i++)
		mascara |= leds[i];
	return mascara;
}

static uint32_t mascara_alarma(unsigned fase)
{
	return (fase & 1u) ? (BIT(LED_2) | BIT(LED_4)) : (BIT(LED_1) | BIT(LED_3));
}

static estado_t estado_siguiente(estado_t actual, int32_t temp_c100, int32_t umbral_c100, int hay_pausa)
{
	switch (actual) {
	case PAUSADO:
		return hay_pausa ? VIGILANDO : PAUSADO;
	case VIGILANDO:
		if (hay_pausa)
			return PAUSADO;
		if (temp_c100 >= umbral_c100)
			return ALARMA;
		return VIGILANDO;
	case ALARMA:
		if (hay_pausa)
			return PAUSADO;
		if (temp_c100 <= umbral_c100 - HISTERESIS_C100)
			return VIGILANDO;
		return ALARMA;
	}
	return actual;
}

static int formatear_registro(char *dst, size_t n, uint32_t t_ms, int32_t temp_c100, int32_t umbral_c100, estado_t e)
{
	const char *nombre = (e == PAUSADO) ? "PAUSADO" : (e == VIGILANDO) ? "VIGILANDO" : "ALARMA";

	return snprintf(dst, n, "%lu,%ld,%ld,%s\n", (unsigned long)t_ms, (long)temp_c100,
			(long)umbral_c100, nombre);
}

#endif