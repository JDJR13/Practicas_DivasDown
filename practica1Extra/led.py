from machine import Pin
import time

led = Pin("LED", Pin.OUT)

for _ in range(10):
    led.toggle()
    time.sleep(0.5)

led.off()
print("LED integrado controlado desde GPIO")