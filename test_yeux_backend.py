import time

from yeux_input_contract import YeuxMouseEvent
from yeux_input_backend import create_backend


backend = create_backend("sendinput")

print("Teste começando em 2 segundos...")
time.sleep(2)

print("Movendo para direita...")
backend.send_event(YeuxMouseEvent(dx=80, dy=0, left=False))
time.sleep(0.3)

print("Movendo para baixo...")
backend.send_event(YeuxMouseEvent(dx=0, dy=80, left=False))
time.sleep(0.3)

print("Movendo para esquerda...")
backend.send_event(YeuxMouseEvent(dx=-80, dy=0, left=False))
time.sleep(0.3)

print("Movendo para cima...")
backend.send_event(YeuxMouseEvent(dx=0, dy=-80, left=False))
time.sleep(0.5)

print("Clique esquerdo em 1 segundo...")
time.sleep(1)

backend.send_event(YeuxMouseEvent(dx=0, dy=0, left=True))

print("Finalizado.")