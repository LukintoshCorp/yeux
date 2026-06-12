import time
import winsound
from pathlib import Path


class YeuxSoundSystem:
    def __init__(self, sounds_dir="sounds"):
        base_dir = Path(__file__).resolve().parent
        self.sounds_dir = base_dir / sounds_dir

        self.sounds = {
            "success": self.sounds_dir / "acao_concluida.wav",
            "error": self.sounds_dir / "erro.wav",
            "click": self.sounds_dir / "acao_concluida.wav",
            "calibration": self.sounds_dir / "acao_concluida.wav",
            "tracking_lost": self.sounds_dir / "erro.wav",
            "tracking_found": self.sounds_dir / "acao_concluida.wav",
        }

        self.cooldowns = {
            "success": 0.4,
            "error": 1.5,
            "click": 0.25,
            "calibration": 1.0,
            "tracking_lost": 2.5,
            "tracking_found": 1.2,
        }

        self.priority = {
            "error": 4,
            "tracking_lost": 4,
            "calibration": 3,
            "tracking_found": 2,
            "success": 2,
            "click": 1,
        }

        self.last_played = {name: 0 for name in self.sounds}
        self.current_priority = 0
        self.priority_until = 0

    def play(self, sound_type: str):
        now = time.time()

        if sound_type not in self.sounds:
            return

        sound_path = self.sounds[sound_type]

        if not sound_path.exists():
            print(f"[Yeux Sound] Arquivo não encontrado: {sound_path}")
            return

        if now - self.last_played[sound_type] < self.cooldowns[sound_type]:
            return

        if now < self.priority_until:
            if self.priority[sound_type] < self.current_priority:
                return

        try:
            winsound.PlaySound(
                str(sound_path),
                winsound.SND_FILENAME | winsound.SND_ASYNC
            )

            self.last_played[sound_type] = now
            self.current_priority = self.priority[sound_type]
            self.priority_until = now + 0.25

        except Exception as e:
            print("[Yeux Sound] Erro ao tocar som:", e)

    def update(self):
        if time.time() >= self.priority_until:
            self.current_priority = 0

    def stop(self):
        winsound.PlaySound(None, winsound.SND_PURGE)


if __name__ == "__main__":
    sound = YeuxSoundSystem()

    print("Testando click...")
    sound.play("click")
    time.sleep(1)

    print("Testando calibração...")
    sound.play("calibration")
    time.sleep(1)

    print("Testando erro...")
    sound.play("tracking_lost")
    time.sleep(1)

    print("Teste finalizado.")