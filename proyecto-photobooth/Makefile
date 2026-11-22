# El Fotobut · atajos para no recordar comandos. Cada objetivo solo llama a un script del proyecto.
#   make simular     prueba todo en cualquier PC, sin hardware (abre http://127.0.0.1:8000)
#   make probar      corre las pruebas automaticas
#   make instalar    instala la cabina en una Raspberry Pi recien grabada (pide sudo; necesita internet)
#   make firmware    compila el firmware del STM32       make flash-stm32   lo graba por UART desde la Pi
#   make auditar     revisa la seguridad en la Pi        make respaldo      respaldo de registros y contador
#   make estado      estado de la cabina en vivo         make limpiar       borra archivos temporales
PY ?= python3

simular:
	$(PY) run.py --sim
probar:
	@set -e; for t in tests/test_*.py; do echo "== $$t"; $(PY) $$t | tail -1; done
instalar:
	sudo ./scripts/instalar.sh
firmware:
	$(MAKE) -C firmware_stm32
flash-stm32:
	$(MAKE) -C firmware_stm32 flash-uart
auditar:
	./tools/pruebas/auditar_seguridad.sh
respaldo:
	./tools/mantenimiento/respaldo.sh
estado:
	./tools/mantenimiento/ver_estado.sh
limpiar:
	find . -name __pycache__ -prune -exec rm -rf {} +

.PHONY: simular probar instalar firmware flash-stm32 auditar respaldo estado limpiar
