import _thread, time

candado = _thread.allocate_lock()

def decir(texto):
    with candado:
        print(texto)

def tarea_nucleo1():
    for i in range(5):
        decir("Núcleo 1 activo, vuelta " + str(i))
        time.sleep(1)

_thread.start_new_thread(tarea_nucleo1, ())

for i in range(5):
    decir("Núcleo 0 activo, vuelta " + str(i))
    time.sleep(1)