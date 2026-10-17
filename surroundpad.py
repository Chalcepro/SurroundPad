"""SurroundPad - play SurrounDead with an Xbox controller.

SurrounDead has no controller support, so this reads the pad through XInput
and presses the game's own keyboard and mouse controls. It only sends input
while the SurrounDead window is in front, so it never types into anything else.

Run:  py -3.12 surroundpad.py          (or double-click SurroundPad.bat)
Edit bindings in bindings.ini next to this file; restart to apply.
Back + Start together pauses / resumes it.
"""
import configparser
import ctypes
import ctypes.wintypes as wt
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_EXE = "surroundead"  # matched against the front window's process name

# ---------------------------------------------------------------- XInput
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [("wButtons", wt.WORD), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wt.DWORD), ("Gamepad", XINPUT_GAMEPAD)]

for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
    try:
        xinput = ctypes.WinDLL(dll)
        break
    except OSError:
        xinput = None
if xinput is None:
    sys.exit("No XInput DLL found.")

BUTTON_BITS = {
    "DUp": 0x0001, "DDown": 0x0002, "DLeft": 0x0004, "DRight": 0x0008,
    "Start": 0x0010, "Back": 0x0020, "L3": 0x0040, "R3": 0x0080,
    "LB": 0x0100, "RB": 0x0200, "A": 0x1000, "B": 0x2000, "X": 0x4000, "Y": 0x8000,
}

# ---------------------------------------------------------------- SendInput
user32 = ctypes.WinDLL("user32", use_last_error=True)
ULONG_PTR = ctypes.c_size_t

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]

KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8
MOUSE = {"LMB": (0x2, 0x4), "RMB": (0x8, 0x10), "MMB": (0x20, 0x40)}
MOUSEEVENTF_MOVE, MOUSEEVENTF_WHEEL = 0x1, 0x800

# Scan codes (set 1). Extended keys carry 0xE000.
SCAN = {
    "ESC": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08, "8": 0x09,
    "9": 0x0A, "0": 0x0B, "TAB": 0x0F, "Q": 0x10, "W": 0x11, "E": 0x12, "R": 0x13, "T": 0x14, "Y": 0x15,
    "U": 0x16, "I": 0x17, "O": 0x18, "P": 0x19, "ENTER": 0x1C, "LCTRL": 0x1D, "A": 0x1E, "S": 0x1F,
    "D": 0x20, "F": 0x21, "G": 0x22, "H": 0x23, "J": 0x24, "K": 0x25, "L": 0x26, "LSHIFT": 0x2A,
    "Z": 0x2C, "X": 0x2D, "C": 0x2E, "V": 0x2F, "B": 0x30, "N": 0x31, "M": 0x32, "LALT": 0x38,
    "SPACE": 0x39, "CAPS": 0x3A, "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F,
    "F6": 0x40, "F7": 0x41, "F8": 0x42, "F9": 0x43, "F10": 0x44,
    "UP": 0xE048, "DOWN": 0xE050, "LEFT": 0xE04B, "RIGHT": 0xE04D,
}

def send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

def key_input(name, up):
    sc = SCAN[name]
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if sc > 0xFF else 0)
    i = INPUT(type=1)
    i.u.ki = KEYBDINPUT(0, sc & 0xFF, flags, 0, 0)
    return i

def mouse_input(dx=0, dy=0, flags=0, data=0):
    i = INPUT(type=0)
    i.u.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
    return i

def press(action, down):
    """action is a key name, LMB/RMB/MMB, WHEELUP/WHEELDOWN, or empty."""
    if not action:
        return
    if action in MOUSE:
        send(mouse_input(flags=MOUSE[action][0 if down else 1]))
    elif action in ("WHEELUP", "WHEELDOWN"):
        if down:
            send(mouse_input(flags=MOUSEEVENTF_WHEEL, data=120 if action == "WHEELUP" else -120))
    else:
        send(key_input(action, not down))

# ---------------------------------------------------------------- front window check
kernel32 = ctypes.WinDLL("kernel32")
def front_exe():
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    size = wt.DWORD(len(buf))
    ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(h)
    return os.path.basename(buf.value).lower() if ok else ""

# ---------------------------------------------------------------- config
DEFAULT_INI = """\
; SurroundPad bindings. Values: a key (W, LSHIFT, SPACE, E, 1, F, TAB, ESC, ...),
; LMB / RMB / MMB, WHEELUP / WHEELDOWN, or empty for nothing.
; If a button does the wrong thing, check the game's Controls menu and change it here.

[buttons]
A = SPACE
B = C
X = R
Y = E
LB = Q
RB = F
LT = RMB
RT = LMB
L3 = LSHIFT
R3 = V
Back = TAB
Start = ESC
DUp = 1
DRight = 2
DDown = 3
DLeft = 4

[sticks]
; left stick = these four keys
up = W
down = S
left = A
right = D
; how far to push the left stick before it counts (0-1)
move_threshold = 0.35
; L3 sprint stays on until you stop moving (true) or only while held (false)
sprint_toggle = true

[look]
; right stick turn speed in pixels per second at full tilt
speed = 1400
; 1 = linear, 2 = fine control near centre
curve = 2.0
invert_y = false
deadzone = 0.15
trigger_threshold = 0.25
"""

def load_config():
    path = os.path.join(HERE, "bindings.ini")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_INI)
    cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
    cp.optionxform = str
    cp.read(path, encoding="utf-8")
    buttons = {k: v.strip().upper() for k, v in cp["buttons"].items()}
    for v in list(buttons.values()) + [cp["sticks"][k].strip().upper() for k in ("up", "down", "left", "right")]:
        if v and v not in SCAN and v not in MOUSE and v not in ("WHEELUP", "WHEELDOWN"):
            sys.exit(f"bindings.ini: unknown key '{v}'. Known: {', '.join(sorted(SCAN))}, LMB, RMB, MMB, WHEELUP, WHEELDOWN")
    return cp, buttons, path

# ---------------------------------------------------------------- main loop
def dead(v, dz):
    v = max(-1.0, v / 32767.0)
    a = abs(v)
    return 0.0 if a < dz else math.copysign((a - dz) / (1 - dz), v)

def main():
    cp, buttons, path = load_config()
    st, lk = cp["sticks"], cp["look"]
    stick_keys = {"up": st["up"].strip().upper(), "down": st["down"].strip().upper(),
                  "left": st["left"].strip().upper(), "right": st["right"].strip().upper()}
    move_t = float(st["move_threshold"])
    sprint_toggle = st.getboolean("sprint_toggle")
    speed, curve = float(lk["speed"]), float(lk["curve"])
    inv = -1 if lk.getboolean("invert_y") else 1
    dz, trig_t = float(lk["deadzone"]), float(lk["trigger_threshold"])

    print(f"SurroundPad running. Bindings: {path}")
    print("Waiting for the controller and for SurrounDead to be in front. Back+Start pauses. Ctrl+C quits.")

    held = set()           # actions currently held down by us
    prev = {}              # control -> was pressed last frame
    sprint_latched = False
    paused = False
    combo_prev = False
    carry_x = carry_y = 0.0
    state = XINPUT_STATE()
    pad = -1
    last = time.perf_counter()
    was_active = False

    def release_all():
        nonlocal sprint_latched
        for a in list(held):
            press(a, False)
        held.clear()
        prev.clear()
        sprint_latched = False

    def want(action, on):
        if not action:
            return
        if on and action not in held:
            held.add(action); press(action, True)
        elif not on and action in held:
            held.discard(action); press(action, False)

    try:
        while True:
            time.sleep(0.004)
            now = time.perf_counter()
            dt = min(0.05, now - last)
            last = now

            if pad < 0:
                for i in range(4):
                    if xinput.XInputGetState(i, ctypes.byref(state)) == 0:
                        pad = i
                        print(f"Controller {i + 1} connected.")
                        break
                else:
                    time.sleep(0.5)
                    continue
            if xinput.XInputGetState(pad, ctypes.byref(state)) != 0:
                print("Controller disconnected.")
                pad = -1
                release_all()
                continue
            g = state.Gamepad

            combo = bool(g.wButtons & BUTTON_BITS["Back"]) and bool(g.wButtons & BUTTON_BITS["Start"])
            if combo and not combo_prev:
                paused = not paused
                release_all()
                print("Paused." if paused else "Resumed.")
            combo_prev = combo

            active = not paused and GAME_EXE in front_exe()
            if active != was_active:
                if not active:
                    release_all()
                print("SurrounDead in front - controller live." if active else "Not in SurrounDead - controller idle.")
                was_active = active
            if not active or combo:
                continue

            # buttons
            for name, bit in BUTTON_BITS.items():
                if name in ("L3",):
                    continue
                want(buttons.get(name, ""), bool(g.wButtons & bit))
            want(buttons.get("LT", ""), g.bLeftTrigger / 255 > trig_t)
            want(buttons.get("RT", ""), g.bRightTrigger / 255 > trig_t)

            # left stick -> movement keys
            lx, ly = dead(g.sThumbLX, dz), dead(g.sThumbLY, dz)
            want(stick_keys["up"], ly > move_t)
            want(stick_keys["down"], ly < -move_t)
            want(stick_keys["right"], lx > move_t)
            want(stick_keys["left"], lx < -move_t)

            # L3 sprint: latch until the stick returns to centre
            l3 = bool(g.wButtons & BUTTON_BITS["L3"])
            moving = abs(lx) > move_t or abs(ly) > move_t
            if sprint_toggle:
                if l3 and not prev.get("L3"):
                    sprint_latched = not sprint_latched
                if not moving:
                    sprint_latched = False
                want(buttons.get("L3", ""), sprint_latched)
            else:
                want(buttons.get("L3", ""), l3)
            prev["L3"] = l3

            # right stick -> mouse movement (also moves the cursor in menus)
            rx, ry = dead(g.sThumbRX, dz), dead(g.sThumbRY, dz)
            if rx or ry:
                carry_x += math.copysign(abs(rx) ** curve, rx) * speed * dt
                carry_y += -math.copysign(abs(ry) ** curve, ry) * speed * dt * inv
                mx, my = int(carry_x), int(carry_y)
                carry_x -= mx; carry_y -= my
                if mx or my:
                    send(mouse_input(mx, my, MOUSEEVENTF_MOVE))
    except KeyboardInterrupt:
        pass
    finally:
        release_all()
        print("SurroundPad stopped.")

if __name__ == "__main__":
    main()
