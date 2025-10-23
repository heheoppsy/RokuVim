```
 ██████╗  ██████╗ ██╗  ██╗██╗   ██╗██╗   ██╗██╗███╗   ███╗
 ██╔══██╗██╔═══██╗██║ ██╔╝██║   ██║██║   ██║██║████╗ ████║
 ██████╔╝██║   ██║█████╔╝ ██║   ██║██║   ██║██║██╔████╔██║
 ██╔══██╗██║   ██║██╔═██╗ ██║   ██║╚██╗ ██╔╝██║██║╚██╔╝██║
 ██║  ██║╚██████╔╝██║  ██╗╚██████╔╝ ╚████╔╝ ██║██║ ╚═╝ ██║
 ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝
```
#### Add Vim bindings to local network Roku devices
[![PyPI](https://img.shields.io/pypi/v/rokuvim.svg)](https://pypi.org/project/rokuvim/)

----

This project uses the Roku external control API
(https://developer.roku.com/docs/developer-program/debugging/external-control-api.md)

It automatically scans the local network for Roku devices and lets you control them from your terminal, using common Vim bindings.

Includes text input (insert mode), media control and device/media information.

----

Decided to revive this and fix some of the rendering issues.  Uses curses for rendering.

----

## Installation

### From PyPI
`pip install rokuvim`

### From source

```bash
git clone https://github.com/heheoppsy/RokuVim.git
cd RokuVim
pip install .
```

After installing, launch the remote with:  `rokuvim`

----

## Notes
Roku has disabled network remote support by default on newer devices.  You'll have to enable them.

From the home screen go to Settings > System > Advanced System settings > Control by mobile apps > Network Access and change the setting to "Enabled". A warning will come up, select "Yes, allow".

HTTP requests are handled with `requests`; no additional system libraries are required.
The curses UI requires a real TTY; some IDE terminals or non-interactive shells may fail.
