# SurroundPad

Play SurrounDead with an Xbox controller. The game has no controller support,
so this reads the pad through XInput and presses the game's keyboard and mouse
controls. It only sends input while the SurrounDead window is in front.

Run `SurroundPad.bat` (needs Python 3.12 via the `py` launcher), then start the game.
Back + Start together pauses/resumes. Bindings live in `bindings.ini` (created on first run).

| Pad | Default |
|---|---|
| Left stick | W A S D |
| Right stick | mouse look (also moves the menu cursor) |
| RT / LT | left click (attack) / right click (aim) |
| A / B / X / Y | Space / C / R / E |
| LB / RB | Q / F |
| L3 | Shift (sprint, stays on until you stop) |
| R3 | V |
| D-pad | 1 2 3 4 |
| Back / Start | Tab / Esc |

If a button does the wrong thing, check the game's Controls menu and change the
key in `bindings.ini`.
