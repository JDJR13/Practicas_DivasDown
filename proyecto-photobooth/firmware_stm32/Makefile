# Uso (en la Raspberry Pi):  sudo apt install gcc-arm-none-eabi stlink-tools
#   make          -> build/smartbooth_stm32.elf/.bin
#   make flash    -> graba con ST-Link (st-flash)
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
flash: $(OUT).bin
	st-flash --connect-under-reset write $(OUT).bin 0x8000000
clean:
	rm -rf build
.PHONY: all flash clean
