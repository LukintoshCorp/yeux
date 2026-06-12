import subprocess
import time
import os
import sys

BASE = r"C:\Users\lucas\Videos\mouse-invisível"
YEUX = os.path.join(BASE, "yeux.py")

while True:
    subprocess.run(
        [sys.executable, YEUX, "--headless"],
        cwd=BASE,
        check=False,
    )
    time.sleep(2)