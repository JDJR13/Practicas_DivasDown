import os, gc, machine, time, network

# Hora por Wi-Fi (NTP). Si falla, usa la hora por defecto de la placa
try:
    import secrets, ntptime
    network.country("MX")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(secrets.SSID, secrets.PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(1)
    ntptime.settime()
except Exception as e:
    print("Sin sincronizar hora:", e)

t = time.localtime(time.time() - 6 * 3600)   # UTC-6, hora de México
LOG = "sysinfo_%04d%02d%02d_%02d%02d%02d.log" % t[:6]

def salida(f, texto):
    print(texto)
    f.write(texto + "\n")

with open(LOG, "w") as f:
    salida(f, "=== Reporte generado: %04d-%02d-%02d %02d:%02d:%02d ===" % t[:6])
    salida(f, "--- Sistema ---")
    salida(f, str(os.uname()))
    salida(f, "--- CPU ---")
    salida(f, "Frecuencia: %d MHz" % (machine.freq() // 1000000))
    gc.collect()
    salida(f, "--- Memoria ---")
    salida(f, "Libre: %d KB  Usada: %d KB" % (gc.mem_free() // 1024, gc.mem_alloc() // 1024))
    s = os.statvfs("/")
    salida(f, "--- Disco ---")
    salida(f, "Flash libre: %d KB de %d KB" % (s[0] * s[3] // 1024, s[0] * s[2] // 1024))

print("Reporte guardado en:", LOG)