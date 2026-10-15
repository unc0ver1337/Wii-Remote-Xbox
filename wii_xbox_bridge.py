"""Map a Bluetooth Wii Remote + Nunchuk to one virtual Xbox 360 controller.

Requirements: hidapi, vgamepad, and the ViGEmBus driver. The script uses the
currently paired Nintendo RVL-CNT-01 and leaves the Bluetooth pairing alone.
"""

from __future__ import annotations

import sys
import time

import hid
import vgamepad as vg
from vgamepad.win.vigem_commons import XUSB_BUTTON as XB

VID_NINTENDO = 0x057E
PID_WIIMOTE = 0x0306
REPORT_MODE = 0x34  # Core buttons + extension data (includes Nunchuk)

# Wii Remote button bit masks (decoded as big-endian bytes 1 and 2).
WIIMOTE = {
    "two": 0x0001,
    "one": 0x0002,
    "b": 0x0004,
    "a": 0x0008,
    "minus": 0x0010,
    "home": 0x0080,
    "left": 0x0100,
    "right": 0x0200,
    "down": 0x0400,
    "up": 0x0800,
    "plus": 0x1000,
}

# Requested Xbox mapping. Unlisted buttons are deliberately left unmapped.
BUTTON_MAP = {
    "a": XB.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "b": None,  # analog right trigger
    "one": XB.XUSB_GAMEPAD_START,
    "two": XB.XUSB_GAMEPAD_BACK,
    "minus": XB.XUSB_GAMEPAD_X,
    "plus": XB.XUSB_GAMEPAD_Y,
    "home": None,
    "left": None,
    "right": None,
    "down": None,
    "up": None,
}


def axis(value: int, center: int = 128, deadzone: int = 7) -> int:
    delta = value - center
    if abs(delta) <= deadzone:
        return 0
    span = 128 - deadzone if delta < 0 else 127 - deadzone
    scaled = int((delta - (-(deadzone) if delta < 0 else deadzone)) * 32767 / span)
    return max(-32768, min(32767, scaled))


def find_wiimote() -> dict:
    devices = [d for d in hid.enumerate(VID_NINTENDO, PID_WIIMOTE)]
    if not devices:
        raise RuntimeError("Nintendo RVL-CNT-01 isn't currently connected over Bluetooth.")
    return devices[0]


def main() -> int:
    device_info = find_wiimote()
    remote = hid.device()
    pad = None
    try:
        remote.open_path(device_info["path"])
        remote.set_nonblocking(True)
        # Ask for continuous reports so the virtual controller remains current.
        if remote.write([0x12, 0x04, REPORT_MODE]) <= 0:
            raise RuntimeError("Couldn't set the Wii Remote report mode.")

        pad = vg.VX360Gamepad()
        print("Wii Remote + Nunchuk -> virtual Xbox 360 controller is running.")
        print("Nunchuk stick -> left stick | Wii D-pad -> right stick")
        print("Wii B -> RT | A -> RB | + -> Y | - -> X | 1/2 -> Start/Back")
        print("Nunchuk C/Z -> LB/LT | stick movement also holds L3/R3")
        print("Press Ctrl+C to stop.", flush=True)

        last_report = 0.0
        while True:
            report = remote.read(64, 100)
            if not report:
                continue
            data = bytes(report)
            if data[0] != REPORT_MODE or len(data) < 9:
                continue

            # Reports begin [id, buttons-hi, buttons-lo, ext0..ext5, ...].
            buttons = (data[1] << 8) | data[2]
            stick_x, stick_y = data[3], data[4]
            nunchuk_buttons = data[8]

            pad.reset()
            for name, mask in WIIMOTE.items():
                if buttons & mask and BUTTON_MAP[name] is not None:
                    pad.press_button(BUTTON_MAP[name])
            pad.right_trigger(255 if buttons & WIIMOTE["b"] else 0)

            # Nunchuk C and Z map to LB and LT respectively.
            if not (nunchuk_buttons & 0x02):
                pad.press_button(XB.XUSB_GAMEPAD_LEFT_SHOULDER)
            if not (nunchuk_buttons & 0x01):
                pad.left_trigger(255)

            # User requested inverted vertical axes on both Xbox sticks.
            pad.left_joystick(axis(stick_x), -axis(stick_y))
            nunchuk_stick_pressed = (abs(axis(stick_x)) > 0 or abs(axis(stick_y)) > 0)
            if nunchuk_stick_pressed:
                pad.press_button(XB.XUSB_GAMEPAD_LEFT_THUMB)

            dpad_x = bool(buttons & WIIMOTE["right"]) - bool(buttons & WIIMOTE["left"])
            dpad_y = bool(buttons & WIIMOTE["down"]) - bool(buttons & WIIMOTE["up"])
            pad.right_joystick(dpad_x * 32767, dpad_y * 32767)
            if dpad_x or dpad_y:
                pad.press_button(XB.XUSB_GAMEPAD_RIGHT_THUMB)
            pad.update()

            now = time.monotonic()
            if now - last_report > 2.0:
                last_report = now
    except KeyboardInterrupt:
        print("\nStopping bridge.")
        return 0
    finally:
        if pad is not None:
            pad.reset()
            pad.update()
            del pad
        remote.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Bridge error: {exc}", file=sys.stderr)
        raise SystemExit(1)
