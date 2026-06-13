#!/usr/bin/env python3
import configparser
import datetime
import os
import subprocess
import sys

CACHE = '/tmp/tejas_brightness_cache'
WEBCAM_PROBE = '/tmp/tejas_webcam_ok'

# parse --config early so CONFIG is set before any function uses it
_args = sys.argv[1:]
if '--config' in _args:
    _i = _args.index('--config')
    CONFIG = _args[_i + 1]
    _args = _args[:_i] + _args[_i + 2:]
elif os.path.exists(os.path.expanduser('~/.config/tejas.ini')):
    CONFIG = os.path.expanduser('~/.config/tejas.ini')
else:
    CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tejas.ini')

def load_curve(section):
    cfg = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    cfg.read(CONFIG)
    return sorted((float(k), int(v)) for k, v in cfg[section].items())

def interpolate(curve, x):
    if x <= curve[0][0]:
        return curve[0][1]
    for i in range(len(curve) - 1):
        x0, y0 = curve[i]
        x1, y1 = curve[i + 1]
        if x0 <= x < x1:
            t = (x - x0) / (x1 - x0)
            return int(y0 + t * (y1 - y0))
    return curve[-1][1]

def get_display_count():
    r = subprocess.run(['ddcutil', 'detect', '--brief'], capture_output=True, text=True)
    return max(r.stdout.count('\nDisplay'), 1)

def webcam_luminance():
    try:
        r = subprocess.run(
            ['ffmpeg', '-f', 'v4l2', '-i', '/dev/video0',
             '-frames:v', '1', '-pix_fmt', 'gray8', '-f', 'rawvideo', 'pipe:1'],
            capture_output=True, timeout=10
        )
        if not r.stdout:
            return None
        return sum(r.stdout) / len(r.stdout)
    except Exception:
        return None

def webcam_supported():
    if os.path.exists(WEBCAM_PROBE):
        return open(WEBCAM_PROBE).read().strip() == '1'
    if not os.path.exists('/dev/video0'):
        open(WEBCAM_PROBE, 'w').write('0')
        return False
    result = webcam_luminance() is not None
    open(WEBCAM_PROBE, 'w').write('1' if result else '0')
    return result

def brightness_from_time():
    h = datetime.datetime.now().hour + datetime.datetime.now().minute / 60
    return interpolate(load_curve('time'), h)

def brightness_from_lumen(lum):
    return interpolate(load_curve('webcam-lumen'), lum)

def load_display_offsets():
    cfg = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    cfg.read(CONFIG)
    if 'display-offset' not in cfg:
        return {}
    return {int(k): float(v) for k, v in cfg['display-offset'].items()}

def set_brightness(pct):
    pct = max(5, min(100, int(pct)))
    try:
        cached = int(open(CACHE).read().strip())
        if abs(cached - pct) < 5:
            print(f'  no change (within threshold, cached={cached}%)')
            return
    except Exception:
        pass
    n = get_display_count()
    offsets = load_display_offsets()
    procs = [
        subprocess.Popen(
            ['sudo', 'ddcutil', '--display', str(d), '--noverify', 'setvcp', '10',
             str(max(5, min(100, round(pct * offsets.get(d, 1.0)))))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        for d in range(1, n + 1)
    ]
    bl = '/sys/class/backlight'
    if os.path.isdir(bl):
        for dev in os.listdir(bl):
            try:
                max_b = int(open(f'{bl}/{dev}/max_brightness').read())
                open(f'{bl}/{dev}/brightness', 'w').write(str(int(pct * max_b / 100)))
            except Exception:
                pass
    for p in procs:
        p.wait()
    open(CACHE, 'w').write(str(pct))
    print(f'  set {n} display(s) -> {pct}%')

mode = _args[0] if _args else 'auto'

if mode == 'time':
    pct = brightness_from_time()
    now = datetime.datetime.now().strftime('%H:%M')
    print(f'mode: time | time={now} | brightness={pct}%')
    set_brightness(pct)
elif mode == 'webcam':
    lum = webcam_luminance()
    if lum is not None:
        pct = brightness_from_lumen(lum)
        print(f'mode: webcam | lumen={lum:.1f}/255 | brightness={pct}%')
        set_brightness(pct)
    else:
        pct = brightness_from_time()
        now = datetime.datetime.now().strftime('%H:%M')
        print(f'mode: webcam (capture failed, fallback time) | time={now} | brightness={pct}%')
        set_brightness(pct)
else:
    if webcam_supported():
        lum = webcam_luminance()
        if lum is not None:
            pct = brightness_from_lumen(lum)
            print(f'mode: webcam | lumen={lum:.1f}/255 | brightness={pct}%')
            set_brightness(pct)
        else:
            pct = brightness_from_time()
            now = datetime.datetime.now().strftime('%H:%M')
            print(f'mode: time (webcam read failed) | time={now} | brightness={pct}%')
            set_brightness(pct)
    else:
        pct = brightness_from_time()
        now = datetime.datetime.now().strftime('%H:%M')
        print(f'mode: time (no webcam) | time={now} | brightness={pct}%')
        set_brightness(pct)
