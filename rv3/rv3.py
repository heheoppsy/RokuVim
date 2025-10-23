import sys
import socket
import signal
import time
import re
import threading
from threading import Thread
from queue import Queue
import xml.etree.ElementTree as ET
import html
import curses
from pathlib import Path
from importlib import import_module
import requests

package_dir = Path(__file__).resolve().parent
parent_dir = str(package_dir.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __package__ in (None, ""):
    __package__ = "rv3"
    display = import_module("rv3.display")
else:
    display = import_module(__package__ + ".display")

header_segments = display.header_segments
scanning_segments = display.scanning_segments
selection_header_segments = display.selection_header_segments
selection_body_segments = display.selection_body_segments
selection_footer_segments = display.selection_footer_segments
selected_block_segments = display.selected_block_segments
remote_control_segments = display.remote_control_segments
remote_footer_segments = display.remote_footer_segments
insert_frame_segments = display.insert_frame_segments
error_segments = display.error_segments
blank_line = display.blank_line


SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'RokuVim'})


class device:
    instances = dict()

    def __init__(self, id, ip):
        self.__class__.instances[id] = self
        self.ip = ip

        self.devinfo = None
        self.devname = ""
        self.findremote = False
        self.is_tv = ""
        self.last_device_update = 0

        self.medinfo = None
        self.playing = ""
        self.appname = ""
        self.duration = None
        self.position = None
        self.last_media_update = 0

        self.update_device()
        self.update_media()

        self.t = Thread(target=self.t_updater)
        self.t.daemon = True
        self.t.start()

    def t_updater(self):
        while True:
            self.update_media()
            if time.monotonic() - self.last_device_update > 30:
                self.update_device()
            time.sleep(2)

    def update_device(self):
        self.devinfo = None

        try:
            resp = SESSION.get(
                f'http://{self.ip}:8060/query/device-info',
                timeout=3
            )
            resp.raise_for_status()

            self.devinfo = resp.content

            tree = ET.fromstring(self.devinfo.decode('iso-8859-1', errors='replace'))

            name_node = tree.find("friendly-device-name")
            if name_node is not None and name_node.text:
                self.devname = html.unescape(name_node.text.strip())
            else:
                self.devname = "Unknown"

            tv_node = tree.find("is-tv")
            tv_value = tv_node.text.lower() if tv_node is not None and tv_node.text else ""
            self.is_tv = "TV" if 'true' in tv_value else "BOX"

            fr_node = tree.find("supports-find-remote")
            fr_value = fr_node.text.lower() if fr_node is not None and fr_node.text else ""
            self.findremote = True if 'true' in fr_value else False

            self.last_device_update = time.monotonic()

        except Exception:
            self.err_upd(device=True)

    def update_media(self):
        self.medinfo = None

        try:
            resp = SESSION.get(
                f'http://{self.ip}:8060/query/media-player',
                timeout=3
            )
            resp.raise_for_status()

            self.medinfo = resp.content

            tree = ET.fromstring(self.medinfo.decode('iso-8859-1', errors='replace'))
            state_raw = tree.attrib.get("state", "").lower()
            states = {
                'none': 'Off / Idle',
                'close': 'Nothing playing',
                'open': 'Nothing playing',
                'pause': 'Paused',
                'play': 'Playing',
                'stop': 'Stopped',
                'stopped': 'Stopped',
                'buffering': 'Buffering'
            }
            if state_raw:
                self.playing = states.get(state_raw, state_raw.replace('-', ' ').title())
            else:
                self.playing = "Unknown"

            plugin = tree.find("plugin")
            if plugin is not None:
                name = plugin.attrib.get("name", "")
                self.appname = html.unescape(name) if name else 'None'
            else:
                self.appname = 'None'

            def parse_ms(node_name):
                node = tree.find(node_name)
                if node is None or not node.text:
                    return None
                raw = node.text.split(" ")[0].strip()
                try:
                    return int(raw)
                except ValueError:
                    return None

            self.duration = parse_ms("duration")
            self.position = parse_ms("position")

            if self.appname and 'menu' in self.appname.lower():
                self.appname = 'Menu'

            self.last_media_update = time.monotonic()

        except Exception:
            self.err_upd()

    def err_upd(self, device=False):
        if device:
            self.devinfo = None
            if not self.devname:
                self.devname = "ERR"
            self.findremote = False
            self.is_tv = "ERR"
            self.last_device_update = 0

        self.medinfo = None
        self.playing = "ERR"
        self.appname = "ERR"
        self.duration = None
        self.position = None
        self.last_media_update = 0
        threading.Timer(5, self.update_device).start()


class sets:
    local_ip = None
    active = list()
    select = None
    locker = threading.Lock()
    q = Queue()
    mode = 's'


REMOTE_KEYS = {
    'h': 'Left',
    'j': 'Down',
    'k': 'Up',
    'l': 'Right',
    '[': 'VolumeDown',
    ']': 'VolumeUp',
    'm': 'VolumeMute',
    'o': 'Info',
    'f': 'ChannelUp',
    'd': 'ChannelDown',
    'x': 'PowerOn',
    'z': 'PowerOff',
    ' ': 'Play',
    'b': 'FindRemote',
    '\t': 'Home',
    '\n': 'Select',
    '\x7f': 'Back'
}


COLOR_ATTRS = {}


def init_color_pairs():
    COLOR_ATTRS.clear()
    if not curses.has_colors():
        COLOR_ATTRS[None] = curses.A_NORMAL
        return

    curses.start_color()
    curses.use_default_colors()
    palette = [
        ('black', curses.COLOR_BLACK),
        ('red', curses.COLOR_RED),
        ('green', curses.COLOR_GREEN),
        ('yellow', curses.COLOR_YELLOW),
        ('blue', curses.COLOR_BLUE),
        ('magenta', curses.COLOR_MAGENTA),
        ('cyan', curses.COLOR_CYAN),
        ('white', curses.COLOR_WHITE)
    ]
    for idx, (name, color) in enumerate(palette, start=1):
        curses.init_pair(idx, color, -1)
        COLOR_ATTRS[name] = curses.color_pair(idx)
    COLOR_ATTRS[None] = curses.color_pair(0)


def get_attr(color=None, bold=False):
    base = COLOR_ATTRS.get(color, COLOR_ATTRS.get(None, curses.color_pair(0)))
    if bold:
        base |= curses.A_BOLD
    return base


def write_segments(stdscr, y, segments, start_x=0):
    max_y, max_x = stdscr.getmaxyx()
    if y >= max_y:
        return y + 1

    x = start_x
    for text, color, bold in segments:
        if not text:
            continue
        attr = get_attr(color, bold)
        remaining = max_x - x
        if remaining <= 0:
            break
        snippet = text[:remaining]
        try:
            stdscr.addstr(y, x, snippet, attr)
        except curses.error:
            pass
        x += len(snippet)
    return y + 1


def draw_header(stdscr):
    y = 0
    for line in header_segments(sets.mode):
        y = write_segments(stdscr, y, line)
    return y


def draw_scanning_screen(stdscr, prefix):
    stdscr.erase()
    y = draw_header(stdscr)
    for line in scanning_segments(prefix):
        y = write_segments(stdscr, y, line)
    stdscr.refresh()


def draw_device_selection(stdscr):
    stdscr.erase()
    y = draw_header(stdscr)
    for line in selection_header_segments(len(device.instances)):
        y = write_segments(stdscr, y, line)
    for line in selection_body_segments(device.instances):
        y = write_segments(stdscr, y, line)
    for line in selection_footer_segments():
        y = write_segments(stdscr, y, line)
    stdscr.refresh()


def draw_remote_screen(stdscr, dev):
    stdscr.erase()
    y = draw_header(stdscr)
    for line in selected_block_segments(dev):
        y = write_segments(stdscr, y, line)
    y = write_segments(stdscr, y, blank_line())
    for line in remote_control_segments(dev.findremote):
        y = write_segments(stdscr, y, line)
    y = write_segments(stdscr, y, blank_line())
    for line in remote_footer_segments():
        y = write_segments(stdscr, y, line)
    stdscr.refresh()


def draw_insert_screen(stdscr, dev):
    stdscr.erase()
    y = draw_header(stdscr)
    for line in selected_block_segments(dev):
        y = write_segments(stdscr, y, line)
    y = write_segments(stdscr, y, blank_line())
    for line in insert_frame_segments():
        y = write_segments(stdscr, y, line)
    stdscr.refresh()


def draw_net_error_screen(stdscr):
    stdscr.erase()
    y = draw_header(stdscr)
    for line in error_segments():
        y = write_segments(stdscr, y, line)
    stdscr.refresh()


def translate_key(ch):
    if ch == -1:
        return None
    special = {
        curses.KEY_BACKSPACE: '\x7f',
        127: '\x7f',
        8: '\x7f',
        curses.KEY_ENTER: '\n',
        10: '\n',
        13: '\n',
        curses.KEY_BTAB: '\t',
        9: '\t'
    }
    if ch in special:
        return special[ch]
    if 0 <= ch <= 255:
        return chr(ch)
    return None


def threader():
    while True:
        worker = sets.q.get()
        portscan(worker)
        sets.q.task_done()


def portscan(target):
    socket.setdefaulttimeout(0.25)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex((target, 8060))
        if result == 0:
            with sets.locker:
                sets.active.append(target)
        sock.close()
    except Exception:
        pass


def scan_range(stdscr):
    ip_addr = None
    gateways = ['10.0.0.1', '192.168.0.1', '192.168.1.1']

    for target in gateways:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)
        if sock.connect_ex((target, 80)) == 0:
            ip_addr = sock.getsockname()[0]
            sock.close()
            break
        sock.close()

    if not ip_addr:
        sets.mode = 'e'
        return False

    parts = ip_addr.split('.', 3)
    prefix = '.'.join(parts[:3])
    draw_scanning_screen(stdscr, prefix)

    device.instances = dict()
    sets.active = list()
    sets.select = None

    for _ in range(32):
        t = threading.Thread(target=threader)
        t.daemon = True
        t.start()

    for host in range(2, 256):
        candidate = f"{parts[0]}.{parts[1]}.{parts[2]}.{host}"
        sets.q.put(candidate)

    sets.q.join()

    if len(sets.active) == 0:
        sets.mode = 'e'
        return False

    for idx, addr in enumerate(sets.active, start=1):
        device(idx, addr)

    return True


def c_keypress(key):
    dev = device.instances[sets.select]
    try:
        resp = SESSION.post(
            f'http://{dev.ip}:8060/keypress/{key}',
            timeout=2
        )
        resp.raise_for_status()
    except requests.RequestException:
        pass


def rv_init(stdscr):
    stdscr.nodelay(False)
    if not scan_range(stdscr):
        return

    stdscr.nodelay(True)
    draw_device_selection(stdscr)
    last_draw = time.monotonic()

    while sets.mode == 's':
        now = time.monotonic()
        if now - last_draw > 0.5:
            draw_device_selection(stdscr)
            last_draw = now

        ch = stdscr.getch()
        if ch == -1:
            curses.napms(50)
            continue
        if ch == curses.KEY_RESIZE:
            draw_device_selection(stdscr)
            continue

        key = translate_key(ch)
        if key is None:
            continue

        if len(key) == 1 and key.lower() == 'q':
            sets.mode = '!'
            break
        if len(key) == 1 and key.lower() == 'r':
            stdscr.nodelay(False)
            return
        if key.isdigit():
            idx = int(key)
            if idx in device.instances:
                sets.select = idx
                sets.mode = 'r'
                break

    stdscr.nodelay(False)


def mode_remote(stdscr):
    dev = device.instances.get(sets.select)
    if not dev:
        sets.mode = 's'
        return

    stdscr.nodelay(True)
    draw_remote_screen(stdscr, dev)
    last_draw = time.monotonic()

    while sets.mode == 'r':
        dev = device.instances.get(sets.select)
        if not dev:
            sets.mode = 's'
            break

        now = time.monotonic()
        if now - dev.last_media_update > 3:
            dev.update_media()
        if now - last_draw > 0.25:
            draw_remote_screen(stdscr, dev)
            last_draw = now

        ch = stdscr.getch()
        if ch == -1:
            curses.napms(40)
            continue
        if ch == curses.KEY_RESIZE:
            draw_remote_screen(stdscr, dev)
            continue

        key = translate_key(ch)
        if key is None:
            continue

        lower = key.lower() if len(key) == 1 else key
        if lower == 'r':
            sets.mode = 's'
            break
        if lower == 'i':
            sets.mode = 'i'
            break
        if lower == 'q':
            sets.mode = '!'
            break

        command = REMOTE_KEYS.get(key)
        if command is None:
            command = REMOTE_KEYS.get(lower)
        if command:
            c_keypress(command)

    stdscr.nodelay(False)


def mode_insert(stdscr):
    dev = device.instances.get(sets.select)
    if not dev:
        sets.mode = 's'
        return

    stdscr.nodelay(True)
    regex = re.compile("[ -~]")
    sm_map = {
        ' ': '%20',
        '@': '%40',
        '#': '%23',
        '$': '%24',
        '%': '%25',
        '&': '%26',
        '+': '%2B',
        '=': '%3D',
        ';': '%3B',
        ':': '%3A',
        '?': '%3F',
        '/': '%2F',
        ',': '%2C',
        '"': '%22',
        '\\': '%5C'
    }

    draw_insert_screen(stdscr, dev)
    last_draw = time.monotonic()

    while sets.mode == 'i':
        dev = device.instances.get(sets.select)
        if not dev:
            sets.mode = 's'
            break

        now = time.monotonic()
        if now - dev.last_media_update > 3:
            dev.update_media()
        if now - last_draw > 0.5:
            draw_insert_screen(stdscr, dev)
            last_draw = now

        ch = stdscr.getch()
        if ch == -1:
            curses.napms(40)
            continue
        if ch == curses.KEY_RESIZE:
            draw_insert_screen(stdscr, dev)
            continue

        key = translate_key(ch)
        if key is None:
            continue

        if key == '\x1b':
            sets.mode = 'r'
            break
        if key == '\n':
            c_keypress('Enter')
            continue
        if key == '\x7f':
            c_keypress('Backspace')
            continue
        if len(key) == 1 and regex.match(key):
            payload = sm_map.get(key, key)
            c_keypress(f'Lit_{payload}')

    stdscr.nodelay(False)


def mode_net_error(stdscr):
    stdscr.nodelay(False)
    draw_net_error_screen(stdscr)

    while sets.mode == 'e':
        ch = stdscr.getch()
        if ch == curses.KEY_RESIZE:
            draw_net_error_screen(stdscr)
            continue

        key = translate_key(ch)
        if key is None:
            continue

        if len(key) == 1 and key.lower() == 'r':
            sets.mode = 's'
            return
        else:
            sets.mode = '!'
            return


def signal_handler(sig, frame):
    raise KeyboardInterrupt


def run(stdscr):
    init_color_pairs()
    stdscr.bkgd(' ', curses.color_pair(0))
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.nodelay(False)
    stdscr.keypad(True)

    while True:
        if sets.mode == 's':
            rv_init(stdscr)
        elif sets.mode == 'e':
            mode_net_error(stdscr)
        elif sets.mode == 'r':
            mode_remote(stdscr)
        elif sets.mode == 'i':
            mode_insert(stdscr)

        if sets.mode == '!':
            break

    try:
        curses.curs_set(1)
    except curses.error:
        pass


def main():
    signal.signal(signal.SIGINT, signal_handler)
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        print('\n jeez OKAY so pushy')


if __name__ == "__main__":
    main()
