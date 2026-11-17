"""Hold-to-drive state; a stop requires releasing and pressing a held key again."""
from .protocol import mix_keys


class DriveIntent:
    def __init__(self):
        self.held = set()
        self.motion = set()
        self.manual = False

    def halt(self):
        self.motion.clear()
        self.manual = False

    def press(self, key):
        if key in self.held:
            return
        self.held.add(key)
        if key == "space":
            self.halt()
        elif key in "wasd" and "space" not in self.held:
            self.manual = False
            self.motion.add(key)

    def release(self, key):
        self.held.discard(key)
        self.motion.discard(key)

    def direction(self, key):
        self.halt()
        if "space" not in self.held:
            self.motion.add(key)

    def start_manual(self):
        self.halt()
        self.manual = "space" not in self.held

    def wheels(self, speed, manual_values):
        if "space" in self.held:
            return (0, 0, 0, 0)
        if self.manual:
            return tuple(manual_values)
        return mix_keys(self.motion, speed)
