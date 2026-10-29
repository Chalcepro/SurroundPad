# SurroundPad

Play SurrounDead with an Xbox (XInput) controller. The game has no controller support,
so this reads the pad through XInput and presses the game's keyboard and mouse controls.
It only sends input while the SurrounDead window is in front.

Run `SurroundPad.bat` (needs Python 3.12 via the `py` launcher), then start the game.
A small always-on-top window lists every control and lights up what you're pressing;
close it and the pad keeps working. Back + Start together pauses/resumes.

While the game runs, `freeze_log.txt` gets a line every 10 s, and one a second whenever the game stops
answering Windows (with its CPU, disk reads and memory), so a freeze shows whether the game hung,
the whole PC stalled, or the controller dropped first.

Keys follow the game's defaults from the [SurrounDead wiki](https://surroundead.wiki.gg/wiki/Controls).
Bindings live in `bindings.ini` (created on first run; an older version is moved to `bindings.ini.old`).

| Pad | Normal | Hold LB + |
|---|---|---|
| Left stick | move (W A S D) | |
| Right stick | look / menu cursor | |
| RT | attack / fire (LMB) | scope zoom (MMB) |
| LT | aim (RMB) | throwable (G) |
| A | jump / vault (Space) | roll (C) |
| B | crouch (Left Ctrl) | radial menu (Z) |
| X | reload (R) | fire mode (X) |
| Y | inventory (Tab) | loot all (E) |
| RB | interact (F) | flashlight / car lights (L) |
| L-stick click | sprint, stays on while moving (Shift) | auto walk (=) |
| R-stick click | shove / stomp (V) | camera view (T) |
| D-pad up / right / down / left | primary / secondary / sidearm / melee (1-4) | night vision / binoculars / sit / journal |
| Back | map (M) | weapon attachment (K) |
| Start | pause menu (Esc) | quick save (F5) |

