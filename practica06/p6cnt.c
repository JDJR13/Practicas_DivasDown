#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/fs.h>
#include <linux/init.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/uaccess.h>
#include <linux/string.h>

static int contador;
static DEFINE_MUTEX(candado);

static int p6c_open(struct inode *inode, struct file *f)
{
    pr_info("open (pid %d, proceso %s)\n", current->pid, current->comm);
    return 0;
}

static ssize_t p6c_read(struct file *f, char __user *dst, size_t n, loff_t *pos)
{
    char linea[32];
    int len;
    ssize_t r;

    mutex_lock(&candado);
    if (*pos == 0)
        contador++;
    len = snprintf(linea, sizeof(linea), "aperturas: %d\n", contador);
    mutex_unlock(&candado);

    r = simple_read_from_buffer(dst, n, pos, linea, len);
    return r;
}

static ssize_t p6c_write(struct file *f, const char __user *src, size_t n,
             loff_t *pos)
{
    char tmp[16];
    size_t copiar = n;

    if (copiar >= sizeof(tmp))
        copiar = sizeof(tmp) - 1;

    if (copy_from_user(tmp, src, copiar))
        return -EFAULT;
    tmp[copiar] = '\0';

    /* Quitar salto de linea final si viene */
    if (copiar > 0 && tmp[copiar - 1] == '\n')
        tmp[copiar - 1] = '\0';

    if (strcmp(tmp, "reset") != 0) {
        /* EINVAL: argumento invalido. Es el codigo estandar para
         * indicar que el dato recibido no tiene un formato o
         * contenido valido para la operacion solicitada. */
        return -EINVAL;
    }

    mutex_lock(&candado);
    contador = 0;
    mutex_unlock(&candado);

    pr_info("contador reiniciado a 0 (pid %d)\n", current->pid);
    return n;
}

static const struct file_operations p6c_fops = {
    .owner  = THIS_MODULE,
    .open   = p6c_open,
    .read   = p6c_read,
    .write  = p6c_write,
    .llseek = default_llseek,
};

static struct miscdevice p6c_dev = {
    .minor = MISC_DYNAMIC_MINOR,
    .name  = "p6cnt",
    .fops  = &p6c_fops,
    .mode  = 0666,
};

static int __init p6c_init(void)
{
    int rc = misc_register(&p6c_dev);

    if (rc) {
        pr_err("misc_register fallo: %d\n", rc);
        return rc;
    }
    pr_info("/dev/p6cnt creado, minor %d\n", p6c_dev.minor);
    return 0;
}

static void __exit p6c_exit(void)
{
    misc_deregister(&p6c_dev);
    pr_info("/dev/p6cnt eliminado. Total de aperturas: %d\n", contador);
}

module_init(p6c_init);
module_exit(p6c_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("DivaDown");
MODULE_DESCRIPTION("Practica 6 FSE: reto final, contador de aperturas");
