import socket
import pycurl
import signal
import time
import sys
import os
import re
import threading
from threading import Thread
from datetime import datetime, timedelta
from curtsies import Input
from queue import Queue
from io import BytesIO
import xml.etree.ElementTree as ET

from colorama import Fore, Back, Style, init
init(autoreset=True)

if os.name == 'nt':
    import msvcrt
    import ctypes

    class _CursorInfo(ctypes.Structure):
        _fields_ = [("size", ctypes.c_int),
                    ("visible", ctypes.c_byte)]

def hide_cursor():
    if os.name == 'nt':
        ci = _CursorInfo()
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.GetConsoleCursorInfo(handle, ctypes.byref(ci))
        ci.visible = False
        ctypes.windll.kernel32.SetConsoleCursorInfo(handle, ctypes.byref(ci))
    elif os.name == 'posix':
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

def show_cursor():
    if os.name == 'nt':
        ci = _CursorInfo()
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.GetConsoleCursorInfo(handle, ctypes.byref(ci))
        ci.visible = True
        ctypes.windll.kernel32.SetConsoleCursorInfo(handle, ctypes.byref(ci))
    elif os.name == 'posix':
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

class c:
    fr = Fore.RED
    fc = Fore.CYAN
    fm = Fore.MAGENTA
    fg = Fore.GREEN
    fw = Fore.WHITE
    fx = Fore.BLACK
    fb = Fore.BLUE
    fy = Fore.YELLOW

    sn = Style.NORMAL
    sb = Style.BRIGHT
    sr = Style.RESET_ALL

class device:
    instances = dict()
    def __init__(self, id, ip):
        self.__class__.instances[id]=self
        self.ip = ip

        self.devinfo = None
        self.devname = ""
        self.findremote = False
        self.is_tv = ""

        self.medinfo = None
        self.playing = ""
        self.appname = ""
        self.duration = None
        self.position = None

        self.update_device()
        self.update_media()

        self.t = Thread(target=self.t_updater)
        self.t.daemon = True
        self.t.start()

    def t_updater(self):
        while True:
            self.update_media()
            time.sleep(2)

    def update_device(self):
        buffer = BytesIO()
        self.devinfo = None

        try:
            c = pycurl.Curl()
            c.setopt(c.USERAGENT, 'RokuVim')
            c.setopt(c.URL, f'http://{self.ip}:8060/query/device-info')
            c.setopt(c.WRITEDATA, buffer)
            c.perform()
            c.close()

            self.devinfo = buffer.getvalue()

            tree = ET.fromstring(self.devinfo.decode('iso-8859-1'))
            self.devname = f'{tree.find("friendly-device-name").text}'

            self.is_tv = f'{tree.find("is-tv").text}'
            self.is_tv = "TV" if 'true' in self.is_tv else "BOX"

            self.findremote = f'{tree.find("supports-find-remote").text}'
            self.findremote = True if 'true' in self.findremote else False

        except:
            self.err_upd()
            pass

    def update_media(self):
            buffer = BytesIO()
            self.medinfo = None

            try:
                c = pycurl.Curl()
                c.setopt(c.USERAGENT, 'RokuVim')
                c.setopt(c.URL, f'http://{self.ip}:8060/query/media-player')
                c.setopt(c.WRITEDATA, buffer)
                c.perform()
                c.close()

                self.medinfo = buffer.getvalue()

                tree = ET.fromstring(self.medinfo.decode('iso-8859-1'))
                self.playing = f'{tree.attrib["state"]}'
                m_state = {
                    'none':'Off / Idle',
                    'close':'Nothing playing',
                    'open':'Nothing playing',
                    'pause':'Paused',
                    'play':'Playing'
                }
                self.playing = m_state[self.playing]

                try:
                    self.appname = f'{tree.find("plugin").attrib["name"]}'
                except:
                    self.appname = 'None'

                try:
                    self.duration = int(tree.find("duration").text.split(" ")[0])
                except:
                    self.duration = None

                try:
                    self.position = int(tree.find("position").text.split(" ")[0])
                except:
                    self.position = None

                if 'Menu' in self.appname:
                    self.appname = 'Menu'

            except:
                self.err_upd()
                pass

    def err_upd(self):
            self.devinfo = None

            self.devname = "ERR"
            self.findremote = False
            self.is_tv = "ERR"

            self.medinfo = None
            self.playing = "ERR"
            self.appname = "ERR"
            self.duration = 1
            self.position = 1
            threading.Timer(5, self.update_device).start()
class sets:
    # Local IP address
    local_ip = None

    # Temporary holding variable for scan
    active = list()

    # Selected device id
    select = None

    # Thread locker
    locker = threading.Lock()

    # Queue for scanning
    q = Queue()

    # Setup for keypress sending
    kp = pycurl.Curl()
    kp.setopt(kp.POST, 1)
    kp.setopt(kp.USERAGENT, 'RokuVim')
    kp.setopt(kp.POSTFIELDS,'')

    # State control because my god do I love doing stuff the HARD way
    mode = 's'
    # setting to s should restart process

def b(x):
    return f'{c.sb}{x}{c.sn}'

def threader():
    while True:
        worker = sets.q.get()
        portscan(worker)
        sets.q.task_done()

def portscan(tar):
    socket.setdefaulttimeout(0.25)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = s.connect_ex((tar,8060))
        if result == 0:
            with sets.locker:
                sets.active.append(tar)
        s.close()
    except:
        pass

# Scan for devices
def scan_range():
    # Update these with common gateways
    # This is to avoid VPN problems
    IP = None
    t = ['10.0.0.1',
         '192.168.0.1',
         '192.168.1.1']

    for x in t:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)

        if s.connect_ex((x, 80)) == 0:
            IP = s.getsockname()[0]
            s.close()
            break

    # This shouldn't happen
    if not IP:
        sets.mode = 'e'
        return

    IP = IP.split(".", 4)
    print(f' {c.fm}Scanning {IP[0]}.{IP[1]}.{IP[2]}.0/24 for Roku devices ..')

    # Reset settings
    device.instances = dict()
    sets.active = list()
    sets.select = None

    for x in range(32):
        t = threading.Thread(target=threader)
        t.daemon = True
        t.start()

    for worker in range(2,256):
        IP[3] = worker
        worker = f"{IP[0]}.{IP[1]}.{IP[2]}.{IP[3]}"
        sets.q.put(worker)

    sets.q.join()

    if len(sets.active) == 0:
        sets.mode = 'e'
        return

    i = 0
    for x in sets.active:
        i += 1
        device(i, x)

    os.system('clear')
    print_header()
    print(f'{c.fm} {b("DONE !")} {len(device.instances)} device(s) found - {c.fc}{b("[R]")} REFRESH\n')
    return True

# Send keypress 
def c_keypress(key):
    x = device.instances[sets.select]
    sets.kp.setopt(sets.kp.URL, f'http://{x.ip}:8060/keypress/{key}')
    sets.kp.perform()

# scan select
def rv_init():
    print_header()

    test = scan_range()
    if not test:
        return

    # print(f'\n {c.sb}{c.fm}Select a device to control:\n')
    for i in device.instances:
        x = device.instances[i]
        if x.appname == "None":
            s = f'{x.playing}'
        else:
            s = f'{x.appname} - {x.playing}'
        print(f' {c.fb}{b(f"[{i}]")} {x.ip} - {x.devname} ({x.is_tv}) \n'\
              f' STATUS: {s}\n')

    print(f' {c.fr}{b("[Q]")} Quit Rokuvim')

    with Input(keynames='curses') as input_generator:
        for e in input_generator:
            s = repr(e).split('\'')[1].lower()

            if s == 'q':
                sets.mode = '!'
                return

            if s == 'r':
                sets.mode = 's'
                return

            try:
                s = int(s)
                if device.instances[s]:
                    sets.select = s
                    sets.mode = 'r'
                    return

            except:
                continue

# Capture KeyboardInterrupt , generally speaking
def signal_handler(sig, frame):
    print('\n Interrupt Captured, be nice')
    show_cursor()
    exit()

###############################################################################

def print_header():
    print('\033[;H')
    a = c.fr if sets.mode == 'e' else c.fm
    b = c.fg

    logo = ""\
          f" {a}██████{b}╗  {a}██████{b}╗ {a}██{b}╗  {a}██{b}╗{a}██{b}╗   {a}██{b}╗{a}██{b}╗   {a}██{b}╗{a}██{b}╗{a}███{b}╗   {a}███{b}╗\n"\
          f" {a}██{b}╔══{a}██{b}╗{a}██{b}╔═══{a}██{b}╗{a}██{b}║ {a}██{b}╔╝{a}██{b}║   {a}██{b}║{a}██{b}║   {a}██{b}║{a}██{b}║{a}████{b}╗ {a}████{b}║\n"\
          f" {a}██████{b}╔╝{a}██{b}║   {a}██{b}║{a}█████{b}╔╝ {a}██{b}║   {a}██{b}║{a}██{b}║   {a}██{b}║{a}██{b}║{a}██{b}╔{a}████{b}╔{a}██{b}║\n"\
          f" {a}██{b}╔══{a}██{b}╗{a}██{b}║   {a}██{b}║{a}██{b}╔═{a}██{b}╗ {a}██{b}║   {a}██{b}║╚{a}██{b}╗ {a}██{b}╔╝{a}██{b}║{a}██{b}║╚{a}██{b}╔╝{a}██{b}║\n"\
          f" {a}██{b}║  {a}██{b}║╚{a}██████{b}╔╝{a}██{b}║  {a}██{b}╗╚{a}██████{b}╔╝ ╚{a}████{b}╔╝ {a}██{b}║{a}██{b}║ ╚═╝ {a}██{b}║\n"\
          f" {b}╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝\n"\
          f" {b}--======= {a}Simple local network Roku remote {b}========-- {c.sb}[{c.fb}{c.sb}{sets.mode.upper()}{b}]\n"
    print(f'{logo}')

def print_selected():
    x = device.instances[sets.select]
    if x.playing == 'Paused' or x.playing == 'Playing':
        try:
            pos = None
            dur = None
            if x.position:
                pos = str(timedelta(milliseconds = x.position)).split('.')[0]
                if pos.split(':')[0] == '0':
                    pos = pos.split(":", 1)[1]

            if x.duration:
                dur = str(timedelta(milliseconds = x.duration)).split('.')[0]
                if dur.split(':')[0] == '0':
                    dur = dur.split(":", 1)[1]

            if dur:
                s = f'{x.appname} - {x.playing} ({pos} : {dur})'
            else:
                s = f'{x.appname} - {x.playing} ({pos})'

        except:
            s = f'{x.appname} - {x.playing} (XX:XX)'
            pass

    else:
        s = f'{x.appname} - {x.playing}'

    print(f' {c.fm}{b(f"SELECTED: ")}{x.ip} - {x.devname} ({x.is_tv})                \n'\
          f' {b("STATUS:")} {s}                      \n')

# REMOTE MODE #################################################################
def mode_remote():
    os.system('clear')
    print_header()
    print_selected()
    print_remote()

    t = Thread(target=refresh_remote)
    t.daemon = True
    t.start()

    in_map = {
        'h':'Left',
        'j':'Down',
        'k':'Up',
        'l':'Right',
        '9':'VolumeDown',
        '0':'VolumeUp',
        'm':'VolumeMute',
        # <THES
        'f':'ChannelUp',
        'd':'ChannelDown',
        # HERE
        'x':'PowerOn',
        'z':'PowerOff',
        ' ':'Play',
        'b':'FindRemote',
        '\\t':'Home',
        '\\n':'Select',
        '\\x7f':'Back'
    }

    # Loop
    with Input(keynames='curses') as input_generator:
        for e in input_generator:
            k = None
            o = repr(e).split('\'')[1].lower()
            if o in in_map:
                k = in_map[o]
            if o == 'r':
                sets.mode = 's'
                return
            elif o == 'i':
                sets.mode = 'i'
                return
            elif o == 'q':
                sets.mode = '!'
                return
            if k:
                c_keypress(k)

def print_remote():
    print(f'{c.fb}'\
          f' {b("[H]")} LEFT      {b("[ENT]")} ENTER\n'\
          f' {b("[J]")} DOWN      {b("[SPC]")} PLAY/PAUSE\n'\
          f' {b("[K]")} UP        {b("[BKS]")} BACK\n'\
          f' {b("[L]")} RIGHT     {b("[TAB]")} HOME\n')

    print(f'{c.fb}'\
          f' {b("[9]")} VOL DOWN  {b("[0]")} VOL UP\n'\
          f' {b("[X]")} POWER ON  {b("[Z]")} POWER OFF\n'\
          f' {b("[M]")} MUTE\n')

    if device.instances[sets.select].findremote:
        print(f' {c.fc}{b("[B]")} FIND REMOTE')

    print(f'{c.fc}'\
          f' {b("[I]")} INSERT MODE\n {b("[R]")} RETURN TO SELECTION\n\n'\
          f' {c.fr}{b("[Q]")} Quit RokuVim')

def refresh_remote():
    while sets.mode == 'r':
        print_header()
        print_selected()
        print_remote()
        time.sleep(2)

# INSERT MODE #################################################################
def mode_insert():

    print_header()
    print_selected()
    print_insert()

    r = re.compile("[ -~]")

    in_map = {
        '\\n':'Enter',
        '\\x7f':'Backspace'
    }

    sm_map = {
        ' ':'%20',
        '@':'%40',
        '#':'%23',
        '$':'%24',
        '%':'%25',
        '&':'%26',
        '+':'%2B',
        '=':'%3D',
        ';':'%3B',
        ':':'%3A',
        '?':'%3F',
        '/':'%2F',
        ',':'%2C',
        '"':'%22',
        '\\':'%5C'
    }

    # Loop
    with Input(keynames='curses') as input_generator:
        for e in input_generator:
            k = None
            o = repr(e).split('\'')[1]

            t = str(o)

            if t == '\\x1b':
                sets.mode = 'r'
                return

            if r.match(t) and len(t) == 1:
                k = f'Lit_{t}'

            if t in in_map:
                k = in_map[t]

            if t in sm_map:
                k = f'Lit_{sm_map[t]}'

            if k:
                c_keypress(k)

def print_insert():
    print(' #########################################################\n'\
          f' ##                      {Fore.RED}INSERT MODE{Style.RESET_ALL}                    ##\n'\
           ' ##                                                     ##\n'\
           ' ##                Esc - Exit insert mode               ##\n'\
           ' #########################################################  ')

###############################################################################
def mode_net_error():
    print_header()
    print(f' {c.sb}{c.fr}Sorry, no device(s) found{c.sn}\n'\
              f'\n{c.fb} Make sure you are connected to the'\
              f'\n same network as your TV or Roku device\n'\
              f'\n Press {b("[R]")} to refresh or any other key to quit')

    with Input(keynames='curses') as input_generator:
        for e in input_generator:
            s = repr(e).split('\'')[1].lower()

            if s == 'r':
                sets.mode = 's'
            else:
                sets.mode = '!'
            return

def main():
    signal.signal(signal.SIGINT, signal_handler)
    hide_cursor()

    while True:
        os.system('clear')
        if sets.mode == 's':
            rv_init()
        elif sets.mode == 'e':
            mode_net_error()
        elif sets.mode == 'r':
            mode_remote()
        elif sets.mode == 'i':
            mode_insert()
        if sets.mode == '!':
            break
    show_cursor()

main()
