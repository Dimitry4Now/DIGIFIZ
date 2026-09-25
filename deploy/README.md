# Running on a Raspberry Pi

## Packages

```bash
sudo apt update
sudo apt install python3-venv python3-pip libsdl2-2.0-0 libsdl2-image-2.0-0 \
                 libsdl2-ttf-2.0-0 libfreetype6
# only if you feed the dash over MQTT
sudo apt install mosquitto mosquitto-clients
```

## Checkout and virtual environment

```bash
git clone <your-fork> ~/DIGIFIZ
cd ~/DIGIFIZ
python3 -m venv .venv
.venv/bin/pip install -U pip -r requirements.txt
```

If you will read an Arduino over USB serial, add your user to the serial group
and log out and back in:

```bash
sudo usermod -aG dialout $USER
```

## Display

The dash takes the panel's own mode and scales the artwork to fit, letterboxing
if the aspect ratio differs. Set the mode in `/boot/firmware/config.txt`; for a
typical 5 inch 800x480 HDMI panel:

```ini
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
disable_overscan=1
```

Check what the dash decided with:

```bash
.venv/bin/python -m digifiz.app --source demo --debug
```

The overlay reports the display size, the scale factor and the letterbox
offset.

## No desktop needed

`SDL_VIDEODRIVER=kmsdrm` draws directly through DRM/KMS, so the Pi can boot to
a console with no X11, no Wayland and no compositor. Boot to console with
`sudo raspi-config` → System Options → Boot / Auto Login → Console.

## Service

```bash
sudo cp deploy/digifiz.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now digifiz
journalctl -u digifiz -f
```

Edit the unit's `Environment=` lines to choose the data source
(`DIGIFIZ_SOURCE=mqtt|serial|demo|obd`) and the broker or serial port.

## Memory

All artwork is decoded and pre-scaled once at startup. At 800x480 that is a few
tens of MB; at the full 1920x720 the process settles around 160 MB resident,
which is comfortable on a 2 GB or larger Pi.

## Surviving power cuts

A cluster gets its power cut rather than shut down. The odometer is written
atomically (temporary file plus rename) and at most once every 30 seconds, so a
cut cannot truncate it. If you want to go further, mount the root filesystem
read-only and keep `odo.txt` on a small writable partition.
