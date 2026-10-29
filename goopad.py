"""GooPad: play World of Goo 2 with an XInput controller (a mouse game, so the
pad drives the cursor). Built on SurroundPad's pad reading and input sending.

  Left stick   move the cursor (push further = faster)
  Right stick  move the cursor fast - push it to a screen edge to look around
  LT (hold)    slow, precise cursor for careful placing
  A (hold)     grab a goo ball; let go to drop it (left mouse)
  B            right mouse
  LB / RB      zoom out / in (mouse wheel)
  Start        menu (Esc)
  Back + Start pause / resume GooPad

It only sends input while WorldOfGoo2.exe is the window in front, and lets
go of everything when you switch away.

World of Goo 2 has its own controller support. If the pad already works in
the game, don't run this as well - you'd get both at once.
"""
import ctypes
import math
import time

from surroundpad import (BUTTON_BITS, MOUSEEVENTF_MOVE, XINPUT_STATE, dead, front_exe, mouse_input, press, send,
                         xinput)

GAME_EXE = "worldofgoo2"
SPEED = 900            # cursor pixels per second, left stick at full tilt
FAST = 1800            # right stick
SLOW = 0.3             # LT held multiplies the speed by this
CURVE = 2.0            # 1 = linear, 2 = fine control near the centre
DEADZONE = 0.15
BUTTONS = {"A": "LMB", "B": "RMB", "Start": "ESC"}
WHEEL_BUTTONS = {"LB": "WHEELDOWN", "RB": "WHEELUP"}
WHEEL_REPEAT = 0.12    # seconds between zoom steps while held


def main():
    state = XINPUT_STATE()
    pad, held = -1, set()
    paused = combo_prev = False
    carry_x = carry_y = 0.0
    wheel_next = 0.0
    last = time.perf_counter()
    status = ""

    def say(s):
        nonlocal status
        if s != status:
            status = s
            print(s, flush=True)

    def apply(wanted):
        for a in list(held - wanted):
            held.discard(a)
            press(a, False)
        for a in wanted - held:
            held.add(a)
            press(a, True)

    try:
        while True:
            time.sleep(0.004)
            now = time.perf_counter()
            dt, last = min(0.05, now - last), now
            if pad < 0:
                pad = next((i for i in range(4) if xinput.XInputGetState(i, ctypes.byref(state)) == 0), -1)
                if pad < 0:
                    say("Waiting for the controller (XInput mode)...")
                    time.sleep(0.5)
                    continue
            if xinput.XInputGetState(pad, ctypes.byref(state)) != 0:
                pad = -1
                apply(set())
                continue
            g = state.Gamepad
            down = {n for n, bit in BUTTON_BITS.items() if g.wButtons & bit}

            combo = "Back" in down and "Start" in down
            if combo and not combo_prev:
                paused = not paused
                apply(set())
            combo_prev = combo
            if paused:
                say("Paused (Back + Start to resume)")
                continue
            if GAME_EXE not in front_exe():
                say("Controller connected - waiting for World of Goo 2 to be in front")
                apply(set())
                continue
            say("Live in World of Goo 2")
            if combo:
                continue

            apply({key for b, key in BUTTONS.items() if b in down})

            wheel = [key for b, key in WHEEL_BUTTONS.items() if b in down]
            if wheel and now >= wheel_next:
                press(wheel[0], True)
                wheel_next = now + WHEEL_REPEAT
            elif not wheel:
                wheel_next = 0.0

            slow = SLOW if g.bLeftTrigger / 255 > 0.25 else 1.0
            vx = vy = 0.0
            for sx, sy, speed in ((g.sThumbLX, g.sThumbLY, SPEED), (g.sThumbRX, g.sThumbRY, FAST)):
                x, y = dead(sx, DEADZONE), dead(sy, DEADZONE)
                vx += math.copysign(abs(x) ** CURVE, x) * speed
                vy -= math.copysign(abs(y) ** CURVE, y) * speed
            carry_x += vx * slow * dt
            carry_y += vy * slow * dt
            mx, my = int(carry_x), int(carry_y)
            carry_x -= mx
            carry_y -= my
            if mx or my:
                send(mouse_input(mx, my, MOUSEEVENTF_MOVE))
    except KeyboardInterrupt:
        pass
    finally:
        apply(set())


if __name__ == "__main__":
    main()
