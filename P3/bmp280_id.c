#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>

#define I2C_ADDR 0x77
#define REG_ID 0xD0

int main(void) {
    int fd = open("/dev/i2c-1", O_RDWR);
    if (fd < 0) { perror("open"); return 1; }

    unsigned char reg = REG_ID;
    unsigned char chip_id = 0;

    struct i2c_msg msgs[2] = {
        {
            .addr = I2C_ADDR,
            .flags = 0,           // escritura
            .len = 1,
            .buf = &reg
        },
        {
            .addr = I2C_ADDR,
            .flags = I2C_M_RD,    // lectura
            .len = 1,
            .buf = &chip_id
        }
    };

    struct i2c_rdwr_ioctl_data data = {
        .msgs = msgs,
        .nmsgs = 2
    };

    if (ioctl(fd, I2C_RDWR, &data) < 0) {
        perror("ioctl I2C_RDWR");
        return 1;
    }

    printf("Chip ID leido: 0x%02X\n", chip_id);
    printf("%s\n", chip_id == 0x58 ? "Es un BMP280 real" : "Algo no cuadra");

    close(fd);
    return 0;
}
