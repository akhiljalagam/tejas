# tejas

> *tejas* (तेजस्) — radiance, brilliance in Sanskrit.

Auto-brightness control for monitors using webcam ambient light or a time-of-day curve.

---

## Why this exists

I tried [clight](https://github.com/FedeDP/Clight), [wluma](https://github.com/maximbaz/wluma), and a few others before writing this. In my experience they felt overly complex to set up, didn't work well with DDC/CI external monitors, and were hard to customize without digging deep into their config formats or source code. I just wanted something I could read, tweak, and trust.

tejas uses `ffmpeg` to grab a webcam frame, averages the pixels, and calls `ddcutil`. You can read the whole script in a few minutes and change whatever you need in `tejas.ini`.

---

## Features

- **Webcam mode** — captures a frame from `/dev/video0`, measures average luminance, maps it to brightness via a configurable curve
- **Time mode** — piecewise linear curve over hours of the day
- **Auto mode** — uses webcam if available, falls back to time
- **DDC/CI** — controls external monitors via `ddcutil setvcp 10`
- **Backlight** — writes to `/sys/class/backlight` if present (laptops)
- **Hysteresis** — skips update if new value is within 5% of last set value
- **Per-display offsets** — multiply each display's target independently (useful when monitors have different base brightness)
- **Stepped transitions** — for jumps >15%, passes through the midpoint first to reduce the perceived snap
- **INI config** — edit anchor points in `tejas.ini`, no code changes needed

---

## Requirements

- Python 3.6+
- [`ddcutil`](https://www.ddcutil.com/) — for external monitor control
- `ffmpeg` — for webcam frame capture (webcam mode only)
- `sudo` access to `ddcutil` (passwordless), or add to `/etc/sudoers.d/ddcutil`:

```
user ALL=(ALL) NOPASSWD: /usr/bin/ddcutil
```

---

## Usage

```sh
python3 tejas.py             # auto: webcam if available, else time
python3 tejas.py time        # force time-based mode
python3 tejas.py webcam      # force webcam mode
python3 tejas.py --config /path/to/custom.ini
python3 tejas.py --config /path/to/custom.ini webcam
```

### Sample output

```
mode: webcam | lumen=83.2/255 | brightness=42%
  set 3 display(s) -> 42%
```

---

## Configuration

Config is looked up in this order:

1. `--config <path>` CLI argument
2. `~/.config/tejas.ini`
3. `tejas.ini` next to the script

```ini
[time]
# hour (0-24) = brightness%
0  = 15
6  = 20
8  = 75
10 = 85
18 = 85
20 = 60
22 = 35
24 = 15

[webcam-lumen]
# luminance (0-255) = brightness%
0   = 5
50  = 20
100 = 40
150 = 65
200 = 85
255 = 100

[display-offset]
# optional: per-display brightness multiplier (display number = multiplier)
# display 2 will be set to 90% of whatever the computed target is
1 = 1.0
2 = 0.9
```

Both `[time]` and `[webcam-lumen]` use piecewise linear interpolation between anchor points. Add or remove rows as needed.

`[display-offset]` is optional. Display numbers match `ddcutil detect` output. Omitting a display defaults to `1.0`.

---

## Scheduling

### cron (every 5 minutes)

```sh
crontab -e
# add:
*/5 * * * * /usr/bin/python3 /path/to/tejas/tejas.py
```

---

## Webcam as a light sensor?

`/dev/video0` doesn't expose an ambient light sensor — it's just a webcam. tejas captures one frame and computes the average pixel brightness as a proxy for room luminance. It's a hack. It works fine in practice unless your webcam is pointed at a wall or the sun. Auto-exposure slightly compresses the dynamic range, but the curve in `tejas.ini` compensates for that.

If your webcam can't be opened or returns no data, tejas silently falls back to the time curve.
