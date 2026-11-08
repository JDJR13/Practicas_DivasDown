import os, gc, machine, ubinascii

def mostrar(etiqueta, valor):
    print("%-16s %s" % (etiqueta + ":", valor))

u = os.uname()
print("=== Reporte del sistema ===")
mostrar("Sistema", u.sysname)
mostrar("Placa", u.machine)
mostrar("Firmware", u.release)

print("\n-- CPU --")
mostrar("Frecuencia", str(machine.freq() // 1000000) + " MHz")
mostrar("ID único", ubinascii.hexlify(machine.unique_id()).decode())

gc.collect()
libre = gc.mem_free()
usada = gc.mem_alloc()
print("\n-- Memoria --")
mostrar("Heap total", str((libre + usada) // 1024) + " KB")
mostrar("Heap libre", str(libre // 1024) + " KB")

s = os.statvfs("/")
print("\n-- Almacenamiento --")
mostrar("Flash total", str(s[0] * s[2] // 1024) + " KB")
mostrar("Flash libre", str(s[0] * s[3] // 1024) + " KB")