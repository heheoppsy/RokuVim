import re
from datetime import timedelta

# Nightmare file
# Don't dead, open inside...

TOKEN = re.compile(r"<<(.*?)>>")
BASE_COLORS = {name: name for name in ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")}

HEADER_LINES = [
    " <<primary>>██████<<secondary>>╗  <<primary>>██████<<secondary>>╗ <<primary>>██<<secondary>>╗  <<primary>>██<<secondary>>╗<<primary>>██<<secondary>>╗   <<primary>>██<<secondary>>╗<<primary>>██<<secondary>>╗   <<primary>>██<<secondary>>╗<<primary>>██<<secondary>>╗<<primary>>███<<secondary>>╗   <<primary>>███<<secondary>>╗",
    " <<primary>>██<<secondary>>╔══<<primary>>██<<secondary>>╗<<primary>>██<<secondary>>╔═══<<primary>>██<<secondary>>╗<<primary>>██<<secondary>>║ <<primary>>██<<secondary>>╔╝<<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║<<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║<<primary>>██<<secondary>>║<<primary>>████<<secondary>>╗ <<primary>>████<<secondary>>║",
    " <<primary>>██████<<secondary>>╔╝<<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║<<primary>>█████<<secondary>>╔╝ <<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║<<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║<<primary>>██<<secondary>>║<<primary>>██<<secondary>>╔<<primary>>████<<secondary>>╔<<primary>>██<<secondary>>║",
    " <<primary>>██<<secondary>>╔══<<primary>>██<<secondary>>╗<<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║<<primary>>██<<secondary>>╔═<<primary>>██<<secondary>>╗ <<primary>>██<<secondary>>║   <<primary>>██<<secondary>>║╚<<primary>>██<<secondary>>╗ <<primary>>██<<secondary>>╔╝<<primary>>██<<secondary>>║<<primary>>██<<secondary>>║╚<<primary>>██<<secondary>>╔╝<<primary>>██<<secondary>>║",
    " <<primary>>██<<secondary>>║  <<primary>>██<<secondary>>║╚<<primary>>██████<<secondary>>╔╝<<primary>>██<<secondary>>║  <<primary>>██<<secondary>>╗╚<<primary>>██████<<secondary>>╔╝ ╚<<primary>>████<<secondary>>╔╝ <<primary>>██<<secondary>>║<<primary>>██<<secondary>>║ ╚═╝ <<primary>>██<<secondary>>║",
    " <<secondary>>╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝",
    " <<secondary>>--======= <<primary>>Simple local network Roku remote <<secondary>>========-- <<blue>><<bold>>[{mode}]<<reset-bold>><<default>>",
]

REMOTE_LINES = [
    " <<blue>><<bold>>[H]<<reset-bold>> LEFT      <<bold>>[ENT]<<reset-bold>> ENTER",
    " <<blue>><<bold>>[J]<<reset-bold>> DOWN      <<bold>>[SPC]<<reset-bold>> PLAY/PAUSE",
    " <<blue>><<bold>>[K]<<reset-bold>> UP        <<bold>>[BKS]<<reset-bold>> BACK",
    " <<blue>><<bold>>[L]<<reset-bold>> RIGHT     <<bold>>[TAB]<<reset-bold>> HOME",
    "",
    " <<blue>><<bold>>[[]<<reset-bold>> VOL DOWN  <<bold>>[]]<<reset-bold>> VOL UP",
    " <<blue>><<bold>>[X]<<reset-bold>> POWER ON  <<bold>>[Z]<<reset-bold>> POWER OFF",
    " <<blue>><<bold>>[M]<<reset-bold>> MUTE      <<bold>>[O]<<reset-bold>> MENU",
]

REMOTE_FIND_LINE = " <<cyan>><<bold>>[B]<<reset-bold>> FIND REMOTE"
REMOTE_FOOTER_LINES = [
    " <<cyan>><<bold>>[I]<<reset-bold>> INSERT MODE",
    " <<cyan>><<bold>>[R]<<reset-bold>> RETURN TO SELECTION",
    "",
    " <<red>><<bold>>[Q]<<reset-bold>> Quit RokuVim",
]

INSERT_FRAME_LINES = [
    " #########################################################",
    " ##                      <<red>><<bold>>INSERT MODE<<reset-bold>><<default>>                    ##",
    " ##                                                     ##",
    " ##                Esc - Exit insert mode               ##",
    " #########################################################  ",
]

ERROR_LINES = [
    " <<red>><<bold>>Sorry, no device(s) found<<reset-bold>><<default>>",
    "",
    " <<blue>> Make sure you are connected to the",
    " <<blue>> same network as your TV or Roku device",
    "",
    "  Press <<cyan>><<bold>>[R]<<reset-bold>><<default>> to refresh or any other key to quit",
]

SCANNING_LINE = " <<magenta>>Scanning {prefix}.0/24 for Roku devices .."
SELECTION_HEADER_LINES = [
    " <<magenta>><<bold>>DONE !<<reset-bold>><<default>> {count} device(s) found - <<cyan>><<bold>>[R]<<reset-bold>><<default>> REFRESH",
    "",
]
SELECTION_ENTRY_LINE = " <<blue>><<bold>>[{index}]<<reset-bold>><<default>> {ip} - {name} ({kind}) "
SELECTION_STATUS_LINE = " STATUS: {status}"
SELECTED_LABEL_LINE = " <<magenta>><<bold>>SELECTED: <<reset-bold>><<default>>{ip} - {name} ({kind})"
SELECTED_STATUS_LINE = " <<magenta>><<bold>>STATUS: <<reset-bold>><<default>>{status}"


def base_palette():
    return dict(BASE_COLORS)


def palette_for_mode(mode):
    colors = base_palette()
    colors["primary"] = "red" if mode == "e" else "magenta"
    colors["secondary"] = "green"
    return colors


def parse_line(line, colors):
    color = None
    bold = False
    cursor = 0
    segments = []
    for match in TOKEN.finditer(line):
        start, end = match.span()
        if start > cursor:
            text = line[cursor:start]
            if text:
                segments.append((text, colors.get(color, color), bold))
        token = match.group(1).strip().lower()
        if token in ("", "/", "reset"):
            color = None
            bold = False
        elif token in ("default", "reset-color"):
            color = None
        elif token in ("bold",):
            bold = True
        elif token in ("reset-bold", "/bold"):
            bold = False
        else:
            if token.startswith("/"):
                color = None
            else:
                color = colors.get(token, token)
        cursor = end
    if cursor < len(line):
        text = line[cursor:]
        if text:
            segments.append((text, colors.get(color, color), bold))
    return segments or [("", None, False)]


def render_line(template, colors, values=None):
    text = template.format(**(values or {}))
    return parse_line(text, colors)


def render_lines(templates, colors, values=None):
    return [render_line(template, colors, values) for template in templates]


def device_status_text(dev):
    if getattr(dev, "playing", None) in ("Paused", "Playing"):
        try:
            pos = None
            dur = None
            if getattr(dev, "position", None) is not None:
                pos = str(timedelta(milliseconds=dev.position)).split(".")[0]
                if pos.split(":")[0] == "0":
                    pos = pos.split(":", 1)[1]
            if getattr(dev, "duration", None) is not None:
                dur = str(timedelta(milliseconds=dev.duration)).split(".")[0]
                if dur.split(":")[0] == "0":
                    dur = dur.split(":", 1)[1]
            pos_disp = pos if pos else "XX:XX"
            if dur:
                return f"{dev.appname} - {dev.playing} ({pos_disp} : {dur})"
            return f"{dev.appname} - {dev.playing} ({pos_disp})"
        except Exception:
            return f"{dev.appname} - {dev.playing} (XX:XX)"
    if getattr(dev, "appname", None) and dev.appname != "None":
        return f"{dev.appname} - {dev.playing}"
    return f"{dev.playing}"


def header_segments(mode):
    return render_lines(HEADER_LINES, palette_for_mode(mode), {"mode": mode.upper()})


def scanning_segments(prefix):
    return [render_line(SCANNING_LINE, base_palette(), {"prefix": prefix})]


def selection_header_segments(count):
    return render_lines(SELECTION_HEADER_LINES, base_palette(), {"count": count})


def selection_body_segments(devices):
    colors = base_palette()
    lines = []
    for index in sorted(devices):
        dev = devices[index]
        status = f"{dev.playing}" if getattr(dev, "appname", None) == "None" else f"{dev.appname} - {dev.playing}"
        lines.append(render_line(SELECTION_ENTRY_LINE, colors, {"index": index, "ip": dev.ip, "name": dev.devname, "kind": dev.is_tv}))
        lines.append(render_line(SELECTION_STATUS_LINE, colors, {"status": status}))
        lines.append(blank_line())
    return lines


def selection_footer_segments():
    return render_lines([" <<red>><<bold>>[Q]<<reset-bold>> Quit RokuVim"], base_palette())


def selected_block_segments(dev):
    colors = base_palette()
    return [
        render_line(SELECTED_LABEL_LINE, colors, {"ip": dev.ip, "name": dev.devname, "kind": dev.is_tv}),
        render_line(SELECTED_STATUS_LINE, colors, {"status": device_status_text(dev)}),
    ]


def remote_control_segments(find_remote):
    colors = base_palette()
    rows = render_lines(REMOTE_LINES, colors)
    if find_remote:
        rows.append(render_line(REMOTE_FIND_LINE, colors))
    return rows


def remote_footer_segments():
    return render_lines(REMOTE_FOOTER_LINES, base_palette())


def insert_frame_segments():
    return render_lines(INSERT_FRAME_LINES, base_palette())


def error_segments():
    return render_lines(ERROR_LINES, base_palette())


def blank_line():
    return [("", None, False)]
