"""SurroundPad - play SurrounDead with an Xbox (XInput) controller.

SurrounDead has no controller support, so this reads the pad through XInput
and presses the game's own keyboard and mouse controls. It only sends input
while the SurrounDead window is in front, so it never types into anything else.

Run:  py -3.12 surroundpad.py          (or double-click SurroundPad.bat)
A small always-on-top window lists the controls; closing it keeps the pad working.
Hold LB for the second layer of buttons. Back + Start together pauses / resumes.
Bindings live in bindings.ini next to this file; restart to apply.
"""
import configparser
import ctypes
import ctypes.wintypes as wt
import math
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_EXE = "surroundead"  # matched against the front window's process name
CONFIG_VERSION = "2"

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
CONTROLS = ["A", "B", "X", "Y", "RB", "LT", "RT", "L3", "R3", "Back", "Start", "DUp", "DRight", "DDown", "DLeft"]

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
    "9": 0x0A, "0": 0x0B, "MINUS": 0x0C, "EQUALS": 0x0D, "TAB": 0x0F, "Q": 0x10, "W": 0x11, "E": 0x12,
    "R": 0x13, "T": 0x14, "Y": 0x15, "U": 0x16, "I": 0x17, "O": 0x18, "P": 0x19, "ENTER": 0x1C,
    "LCTRL": 0x1D, "A": 0x1E, "S": 0x1F, "D": 0x20, "F": 0x21, "G": 0x22, "H": 0x23, "J": 0x24,
    "K": 0x25, "L": 0x26, "SEMICOLON": 0x27, "LSHIFT": 0x2A, "BACKSLASH": 0x2B, "Z": 0x2C, "X": 0x2D,
    "C": 0x2E, "V": 0x2F, "B": 0x30, "N": 0x31, "M": 0x32, "LALT": 0x38, "SPACE": 0x39, "CAPS": 0x3A,
    "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F, "F6": 0x40, "F7": 0x41, "F8": 0x42,
    "F9": 0x43, "F10": 0x44, "UP": 0xE048, "DOWN": 0xE050, "LEFT": 0xE04B, "RIGHT": 0xE04D,
}
WHEEL = ("WHEELUP", "WHEELDOWN")

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
    """action is a key name, LMB/RMB/MMB or WHEELUP/WHEELDOWN."""
    if action in MOUSE:
        send(mouse_input(flags=MOUSE[action][0 if down else 1]))
    elif action in WHEEL:
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
# Defaults follow SurrounDead's default keys (surroundead.wiki.gg/wiki/Controls).
DEFAULT_INI = f"""\
; SurroundPad bindings (version {CONFIG_VERSION}).
; Format:  Button = KEY | label shown in the controls window
; KEY is a key (W, LSHIFT, LCTRL, SPACE, TAB, F, 1, MINUS, EQUALS, ...),
; LMB / RMB / MMB, WHEELUP / WHEELDOWN, or empty for nothing.
; Matches the game's default keys; if you rebind in the game, change it here too.

[buttons]
RT = LMB | Attack / fire
LT = RMB | Aim
A = SPACE | Jump / vault
B = LCTRL | Crouch
X = R | Reload
Y = TAB | Inventory
RB = F | Interact (the F prompt)
L3 = LSHIFT | Sprint (stays on while moving)
R3 = V | Shove / stomp
DUp = 1 | Primary weapon
DRight = 2 | Secondary weapon
DDown = 3 | Sidearm
DLeft = 4 | Melee weapon
Back = M | Map
Start = ESC | Pause menu

; Hold LB, then press:
[buttons_lb]
RT = MMB | Scope zoom
LT = G | Throwable
A = C | Roll
B = Z | Radial menu
X = X | Fire mode
Y = E | Loot all
RB = L | Flashlight / car lights
L3 = EQUALS | Auto walk
R3 = T | Camera view
DUp = N | Night vision
DRight = B | Binoculars
DDown = MINUS | Sit / rest
DLeft = J | Journal
Back = K | Weapon attachment
Start = F5 | Quick save

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

[window]
; show the always-on-top controls list
show = true
"""

def _valid(v):
    return not v or v in SCAN or v in MOUSE or v in WHEEL

def load_config():
    path = os.path.join(HERE, "bindings.ini")
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if f"(version {CONFIG_VERSION})" not in text:
            old = path + ".old"
            os.replace(path, old)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_INI)
    cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
    cp.optionxform = str
    cp.read(path, encoding="utf-8")
    layers = {}
    for sec in ("buttons", "buttons_lb"):
        layer = {}
        for k, v in cp[sec].items():
            key, _, label = v.partition("|")
            key = key.strip().upper()
            if not _valid(key):
                sys.exit(f"bindings.ini [{sec}] {k}: unknown key '{key}'. Known: {', '.join(sorted(SCAN))}, LMB, RMB, MMB, WHEELUP, WHEELDOWN")
            layer[k] = (key, label.strip() or key)
        layers[sec] = layer
    if old:
        print(f"Updated bindings.ini to the game's real keys (your previous file is {old}).")
    return cp, layers, path

# ---------------------------------------------------------------- shared state for the window
class Shared:
    lock = threading.Lock()
    pressed = set()   # control names held right now
    layer = "buttons"
    status = "Starting..."
    stop = False

# ---------------------------------------------------------------- main loop
def dead(v, dz):
    v = max(-1.0, v / 32767.0)
    a = abs(v)
    return 0.0 if a < dz else math.copysign((a - dz) / (1 - dz), v)

def set_status(s):
    with Shared.lock:
        if Shared.status != s:
            Shared.status = s
            print(s)

def run_pad(cp, layers):
    st, lk = cp["sticks"], cp["look"]
    stick_keys = {k: st[k].strip().upper() for k in ("up", "down", "left", "right")}
    move_t = float(st["move_threshold"])
    sprint_toggle = st.getboolean("sprint_toggle")
    speed, curve = float(lk["speed"]), float(lk["curve"])
    inv = -1 if lk.getboolean("invert_y") else 1
    dz, trig_t = float(lk["deadzone"]), float(lk["trigger_threshold"])

    held = set()          # actions currently held down by us
    carried = set()       # controls held through a layer change
    last_layer = "buttons"
    l3_prev = False
    sprint_latched = False
    paused = False
    combo_prev = False
    carry_x = carry_y = 0.0
    state = XINPUT_STATE()
    pad = -1
    last = time.perf_counter()

    def apply(wanted):
        for a in list(held - wanted):
            held.discard(a); press(a, False)
        for a in wanted - held:
            held.add(a); press(a, True)

    set_status("Waiting for the controller...")
    try:
        while not Shared.stop:
            time.sleep(0.004)
            now = time.perf_counter()
            dt = min(0.05, now - last)
            last = now

            if pad < 0:
                for i in range(4):
                    if xinput.XInputGetState(i, ctypes.byref(state)) == 0:
                        pad = i
                        break
                else:
                    set_status("Waiting for the controller (turn it on in XInput mode)...")
                    time.sleep(0.5)
                    continue
            if xinput.XInputGetState(pad, ctypes.byref(state)) != 0:
                pad = -1
                apply(set())
                continue
            g = state.Gamepad
            down = {n for n, bit in BUTTON_BITS.items() if g.wButtons & bit}
            if g.bLeftTrigger / 255 > trig_t: down.add("LT")
            if g.bRightTrigger / 255 > trig_t: down.add("RT")
            layer_name = "buttons_lb" if "LB" in down else "buttons"
            with Shared.lock:
                Shared.pressed, Shared.layer = down, layer_name

            combo = "Back" in down and "Start" in down
            if combo and not combo_prev:
                paused = not paused
                apply(set())
                sprint_latched = False
            combo_prev = combo

            if paused:
                set_status("Paused (Back + Start to resume)")
                continue
            if GAME_EXE not in front_exe():
                set_status("Controller connected - waiting for SurrounDead to be in front")
                apply(set())
                sprint_latched = False
                continue
            set_status("Live in SurrounDead")
            if combo:
                continue

            layer = layers[layer_name]
            # A button held while LB goes down/up keeps quiet until it's pressed again,
            # so letting go of LB+A doesn't also jump.
            if layer_name != last_layer:
                carried = down - {"LB"}
                last_layer = layer_name
            carried &= down
            wanted = set()
            for c in CONTROLS:
                if c == "L3" or c in carried:
                    continue
                if c in down and layer.get(c, ("", ""))[0]:
                    wanted.add(layer[c][0])

            # left stick -> movement keys
            lx, ly = dead(g.sThumbLX, dz), dead(g.sThumbLY, dz)
            moving = abs(lx) > move_t or abs(ly) > move_t
            for k, on in ((stick_keys["up"], ly > move_t), (stick_keys["down"], ly < -move_t),
                          (stick_keys["right"], lx > move_t), (stick_keys["left"], lx < -move_t)):
                if on and k:
                    wanted.add(k)

            # L3: sprint latch on the base layer, a normal button on the LB layer
            l3 = "L3" in down
            l3_key = layer.get("L3", ("", ""))[0]
            if layer_name == "buttons" and sprint_toggle:
                if l3 and not l3_prev:
                    sprint_latched = not sprint_latched
                if not moving:
                    sprint_latched = False
                if sprint_latched and l3_key:
                    wanted.add(l3_key)
            elif l3 and l3_key:
                wanted.add(l3_key)
            l3_prev = l3
            if sprint_latched and layer_name == "buttons_lb":
                wanted.add(layers["buttons"]["L3"][0])

            apply(wanted)

            # right stick -> mouse movement (also moves the cursor in menus)
            rx, ry = dead(g.sThumbRX, dz), dead(g.sThumbRY, dz)
            if rx or ry:
                carry_x += math.copysign(abs(rx) ** curve, rx) * speed * dt
                carry_y += -math.copysign(abs(ry) ** curve, ry) * speed * dt * inv
                mx, my = int(carry_x), int(carry_y)
                carry_x -= mx; carry_y -= my
                if mx or my:
                    send(mouse_input(mx, my, MOUSEEVENTF_MOVE))
    finally:
        apply(set())

# ---------------------------------------------------------------- controls window
def run_window(layers, path):
    import tkinter as tk

    BG, FG, DIM, HI, ACC = "#16181d", "#e8e8e8", "#8a8f98", "#2d6cdf", "#f0b429"
    root = tk.Tk()
    root.title("SurroundPad controls")
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.97)
    root.resizable(False, False)

    status = tk.Label(root, text="", bg=BG, fg=ACC, font=("Segoe UI", 9, "bold"), anchor="w")
    status.pack(fill="x", padx=10, pady=(8, 2))
    tk.Label(root, text="Left stick: move    Right stick: look / cursor", bg=BG, fg=DIM,
             font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=10)

    names = {"RT": "RT", "LT": "LT", "A": "A", "B": "B", "X": "X", "Y": "Y", "RB": "RB",
             "L3": "L-stick click", "R3": "R-stick click", "DUp": "D-pad up", "DRight": "D-pad right",
             "DDown": "D-pad down", "DLeft": "D-pad left", "Back": "Back", "Start": "Start"}
    frame = tk.Frame(root, bg=BG)
    frame.pack(padx=10, pady=6)
    headers = [tk.Label(frame, text=t, bg=BG, fg=DIM, font=("Segoe UI", 9, "bold"), anchor="w")
               for t in ("Button", "Normal", "Hold LB +")]
    for i, h in enumerate(headers):
        h.grid(row=0, column=i, sticky="w", padx=(0, 14))
    cells = {}
    for r, c in enumerate(CONTROLS, start=1):
        tk.Label(frame, text=names[c], bg=BG, fg=FG, font=("Segoe UI", 9, "bold"), anchor="w").grid(
            row=r, column=0, sticky="w", padx=(0, 14))
        for col, layer in ((1, "buttons"), (2, "buttons_lb")):
            key, label = layers[layer].get(c, ("", ""))
            text = f"{label}  [{key.lower()}]" if key else "-"
            lab = tk.Label(frame, text=text, bg=BG, fg=FG, font=("Segoe UI", 9), anchor="w", padx=4)
            lab.grid(row=r, column=col, sticky="w", padx=(0, 10))
            cells[(c, layer)] = lab
    tk.Label(root, text="Back + Start: pause / resume.   Close this window to hide it; the pad keeps working.",
             bg=BG, fg=DIM, font=("Segoe UI", 8), wraplength=430, justify="left").pack(padx=10, pady=(0, 2), anchor="w")
    tk.Label(root, text=f"Edit keys in {path}", bg=BG, fg=DIM, font=("Segoe UI", 8),
             wraplength=430, justify="left").pack(padx=10, pady=(0, 8), anchor="w")

    # Top-right corner, out of the way of the game's centre.
    root.update_idletasks()
    root.geometry(f"+{root.winfo_screenwidth() - root.winfo_reqwidth() - 12}+40")

    def tick():
        with Shared.lock:
            pressed, layer, s = set(Shared.pressed), Shared.layer, Shared.status
        status.config(text=s)
        headers[1].config(fg=ACC if layer == "buttons" else DIM)
        headers[2].config(fg=ACC if layer == "buttons_lb" else DIM)
        for (c, lay), lab in cells.items():
            lab.config(bg=HI if (c in pressed and lay == layer) else BG)
        root.after(50, tick)

    tick()
    root.mainloop()

# ---------------------------------------------------------------- entry
def main():
    cp, layers, path = load_config()
    print(f"SurroundPad running. Bindings: {path}")
    print("Hold LB for the second layer. Back+Start pauses. Ctrl+C or close this terminal to quit.")
    show = cp.getboolean("window", "show", fallback=True)
    if show:
        t = threading.Thread(target=run_pad, args=(cp, layers), daemon=True)
        t.start()
        try:
            run_window(layers, path)
        except Exception as e:
            print(f"(controls window unavailable: {e})")
        print("Controls window closed; the controller keeps working. Ctrl+C to quit.")
        try:
            while t.is_alive():
                t.join(0.5)
        except KeyboardInterrupt:
            pass
        Shared.stop = True
        t.join(2)
    else:
        try:
            run_pad(cp, layers)
        except KeyboardInterrupt:
            pass
    print("SurroundPad stopped.")

if __name__ == "__main__":
    main()
