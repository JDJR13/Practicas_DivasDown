# Uso (en la Raspberry Pi):  sudo apt install gcc-arm-none-eabi stm32flash
#   make             -> build/smartbooth_stm32.elf/.bin
#   make flash-uart  -> graba por UART desde la Pi (lo que usamos: sin ST-Link). Antes: BOOT0=1 y RESET en la placa
#   make flash       -> graba con ST-Link (st-flash), si se tiene uno
PUERTO ?= /dev/ttyAMA0
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
SIZE    = arm-none-eabi-size
CFLAGS  = -mcpu=cortex-m3 -mthumb -Os -Wall -ffreestanding -fno-builtin -ffunction-sections -fdata-sections
LDFLAGS = -nostartfiles -nostdlib -Wl,-T,stm32f103c8.ld -Wl,--gc-sections
OUT     = build/smartbooth_stm32

all: $(OUT).bin
$(OUT).elf: src/main.c src/startup.c stm32f103c8.ld
	@mkdir -p build
	$(CC) $(CFLAGS) $(LDFLAGS) src/main.c src/startup.c -o $@
	$(SIZE) $@
$(OUT).bin: $(OUT).elf
	$(OBJCOPY) -O binary $< $@
flash-uart: $(OUT).bin
	sudo systemctl stop fotobut-control 2>/dev/null || true
	sudo stm32flash -w $(OUT).bin -v -g 0x0 $(PUERTO)
	@echo "Listo: pon BOOT0=0, presiona RESET y luego:  sudo systemctl start fotobut-control"
flash: $(OUT).bin
	st-flash --connect-under-reset write $(OUT).bin 0x8000000
clean:
	rm -rf build
.PHONY: all flash flash-uart clean
