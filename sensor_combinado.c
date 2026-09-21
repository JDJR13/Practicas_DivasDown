#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <linux/spi/spidev.h>
#include <gpiod.h>

#define I2C_ADDR 0x77
#define GPIO_CHIP "gpiochip0"
#define GPIO_LED 17   // <-- AJUSTAR al pin de tu LED en la Practica 2

// --- Variables de calibracion del BMP280 (se leen una vez al iniciar) ---
unsigned short dig_T1;
short dig_T2, dig_T3;

int i2c_fd;

// Lee 'len' bytes empezando en el registro 'reg', usando I2C_RDWR (repeated start)
void i2c_read_regs(unsigned char reg, unsigned char *buf, int len) {
    struct i2c_msg msgs[2] = {
        { .addr = I2C_ADDR, .flags = 0, .len = 1, .buf = &reg },
        { .addr = I2C_ADDR, .flags = I2C_M_RD, .len = len, .buf = buf }
    };
    struct i2c_rdwr_ioctl_data data = { .msgs = msgs, .nmsgs = 2 };
    if (ioctl(i2c_fd, I2C_RDWR, &data) < 0) {
        perror("ioctl I2C_RDWR");
    }
}

void bmp280_leer_calibracion(void) {
    unsigned char buf[6];
    i2c_read_regs(0x88, buf, 6); // registros 0x88-0x8D: dig_T1, dig_T2, dig_T3
    dig_T1 = (buf[1] << 8) | buf[0];
    dig_T2 = (buf[3] << 8) | buf[2];
    dig_T3 = (buf[5] << 8) | buf[4];
}

void bmp280_configurar(void) {
    // ctrl_meas (0xF4): modo normal, oversampling x1 en temperatura y presion
    unsigned char reg = 0xF4;
    unsigned char valor = 0x27;
    unsigned char tx[2] = { reg, valor };
    write(i2c_fd, tx, 2); // aqui si sirve write directo, es escritura simple
}

float bmp280_leer_temperatura(void) {
    unsigned char buf[3];
    i2c_read_regs(0xFA, buf, 3); // registros de temperatura sin compensar

    long adc_T = ((long)buf[0] << 12) | ((long)buf[1] << 4) | (buf[2] >> 4);

    // Formula de compensacion del datasheet Bosch BMP280
    double var1 = (((double)adc_T) / 16384.0 - ((double)dig_T1) / 1024.0) * ((double)dig_T2);
    double var2 = ((((double)adc_T) / 131072.0 - ((double)dig_T1) / 8192.0) *
                   (((double)adc_T) / 131072.0 - ((double)dig_T1) / 8192.0)) * ((double)dig_T3);
    double t_fine = var1 + var2;
    float temperatura = (float)(t_fine / 5120.0);

    return temperatura;
}

int spi_fd;

int leer_potenciometro(void) {
    unsigned char mode = SPI_MODE_0;
    unsigned char bits = 8;
    unsigned int speed = 1000000;

    unsigned char canal = 0;
    unsigned char tx[3] = {1, (8 + canal) << 4, 0};
    unsigned char rx[3] = {0};

    struct spi_ioc_transfer tr = {
        .tx_buf = (unsigned long)tx,
        .rx_buf = (unsigned long)rx,
        .len = 3,
        .speed_hz = speed,
        .bits_per_word = bits,
    };

    ioctl(spi_fd, SPI_IOC_MESSAGE(1), &tr);

    int valor = ((rx[1] & 3) << 8) | rx[2];
    return valor; // 0-1023
}

int main(void) {
    // --- Inicializar I2C ---
    i2c_fd = open("/dev/i2c-1", O_RDWR);
    if (i2c_fd < 0) { perror("open i2c"); return 1; }
    if (ioctl(i2c_fd, I2C_SLAVE, I2C_ADDR) < 0) { perror("ioctl I2C_SLAVE"); return 1; }

    bmp280_configurar();
    bmp280_leer_calibracion();

    // --- Inicializar SPI ---
    spi_fd = open("/dev/spidev0.0", O_RDWR);
    if (spi_fd < 0) { perror("open spi"); return 1; }

    unsigned char mode = SPI_MODE_0;
    unsigned char bits = 8;
    unsigned int speed = 1000000;
    ioctl(spi_fd, SPI_IOC_WR_MODE, &mode);
    ioctl(spi_fd, SPI_IOC_WR_BITS_PER_WORD, &bits);
    ioctl(spi_fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed);

    // --- Inicializar GPIO con libgpiod ---
    struct gpiod_chip *chip = gpiod_chip_open_by_name(GPIO_CHIP);
    if (!chip) { perror("gpiod_chip_open_by_name"); return 1; }

    struct gpiod_line *led = gpiod_chip_get_line(chip, GPIO_LED);
    if (!led) { perror("gpiod_chip_get_line"); return 1; }

    if (gpiod_line_request_output(led, "sensor_combinado", 0) < 0) {
        perror("gpiod_line_request_output");
        return 1;
    }

    float temperatura = bmp280_leer_temperatura();
    time_t ultima_lectura_temp = 0;

    while (1) {
        time_t ahora = time(NULL);

        // Leer temperatura solo cada 2 segundos
        if (ahora - ultima_lectura_temp >= 2) {
            temperatura = bmp280_leer_temperatura();
            ultima_lectura_temp = ahora;
        }

        // Leer potenciometro continuamente como umbral
        int valor_pot = leer_potenciometro();
        float umbral = (valor_pot / 1023.0f) * 50.0f; // mapea 0-1023 a 0-50 C

        printf("Temp: %.2f C | Umbral: %.2f C | ", temperatura, umbral);

        if (temperatura > umbral) {
            gpiod_line_set_value(led, 1);
            printf("LED: ON\n");
        } else {
            gpiod_line_set_value(led, 0);
            printf("LED: OFF\n");
        }

        usleep(300000);
    }

    gpiod_line_release(led);
    gpiod_chip_close(chip);
    close(i2c_fd);
    close(spi_fd);
    return 0;
}
