# MSCZ Library

Local musescore library web interface.

## Prepare

1. Install `musescore`, `Xvfb`
2. Download `musescore.com.squashfs`
3. Prepare a directory, eg. `~/musescore'
4. `mkdir -p ~/musescore/{mscz,ogg,pdf,png}`
5. `sudo mount musescore.com.squashfs ~/musescore/mscz`
6. Install Python dependencies:

```
python3 -mvenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

1. Start `Xvfb :9 -screen 0 1600x1200x24` in the background.
2. Run `venv/bin/python3 mscz_library.py 127.0.0.1:8084`
