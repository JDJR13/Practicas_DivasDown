import os, machine, ubinascii

print("Archivos en la placa:", os.listdir("/"))
print("ID único:", ubinascii.hexlify(machine.unique_id()).decode())
print("Frecuencia CPU (MHz):", machine.freq() // 1000000)