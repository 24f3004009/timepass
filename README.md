# Four-wheel surveillance robot

Two ESP32-CAM boards stream front and rear video over Wi-Fi. One NodeMCU ESP32S receives Bluetooth commands and independently controls four 12 V DC motors through two L298N drivers. A Python PC application displays both cameras and provides keyboard, mouse, and individual-wheel controls.

## Your hardware layout

You have **two ESP32-CAM boards and two NodeMCU ESP32S boards**. This project uses three boards; the second NodeMCU is spare.

| Board | Firmware target | Job |
| --- | --- | --- |
| Front ESP32-CAM | `front` | Front camera → Wi-Fi → PC |
| Rear ESP32-CAM | `rear` | Rear camera → Wi-Fi → PC |
| First NodeMCU ESP32S | `motors` | PC → Bluetooth SPP → four motors |
| Second NodeMCU ESP32S | None | Spare |

The camera firmware targets the common **AI-Thinker ESP32-CAM with an OV2640 ribbon camera**. The motor firmware targets the original **NodeMCU-32S / ESP32-WROOM**, which supports Bluetooth Classic. ESP32-S2, S3 and C3 boards are different targets; S3/C3 do not support Classic SPP. A different ESP32-CAM layout needs its camera pin map changed in `firmware/include/robot_config.h`.

The cameras need no signal wires to the NodeMCU. All three boards communicate directly with the PC. Both cameras and the PC must be on the same local network, with a **2.4 GHz** network available for the cameras. The PC needs Bluetooth Classic SPP support as well as Wi-Fi/Ethernet.

## Wire the robot

The **[data-wiring guide](docs/data-wiring.md)** includes all twelve GPIO connections, shared ground, Wi-Fi/Bluetooth data paths and camera programming connections. Download the **[three-page schematic PDF](docs/diagrams/data-wiring-pack.pdf)** or the individual PNG/SVG diagrams linked in the guide.

Follow **[the wiring and power guide](docs/wiring.md)** before powering the motors. In particular:

- Remove the **ENA and ENB jumpers on both L298Ns**. The NodeMCU drives these four inputs with PWM for independent speed control.
- Fit a **10 kΩ resistor from each EN input to ground** so the bridges stay disabled while the NodeMCU resets or is unplugged.
- Power the cameras and NodeMCU from a regulated **5 V supply**, not the 12 V motor rail. Use a shared ground and separate motor-power wiring.
- Check each motor's **stall current** against the driver and cooling capability. A 12 V rating alone does not establish that an L298N can drive it.

There is one motor per L298N output channel, not two motors wired in parallel on one channel.

## Build and flash

Use Python 3.10+ and PlatformIO, either from its VS Code extension or the command line. The project pins PlatformIO's Espressif platform to `6.9.0` / Arduino ESP32 `2.0.17`.

```sh
python -m venv .venv
# Activate: Windows .venv\Scripts\activate
# Activate: Linux/macOS source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Copy `firmware/include/secrets.example.h` to `firmware/include/secrets.h`. Enter your Wi-Fi SSID/password and change the Bluetooth pairing PIN. `secrets.h` is ignored by Git. Builds without that file use obvious example placeholders and cannot join your real network.

Build all three firmwares:

```sh
pio run
```

Flash each board separately, replacing `COM5` with its **USB programming port**, such as `/dev/ttyUSB0` or `/dev/cu.usbserial-...`:

```sh
pio run -e front --target upload --upload-port COM5
pio run -e rear --target upload --upload-port COM5
pio run -e motors --target upload --upload-port COM5
```

Label the boards as you flash them. Do not upload all targets to the same board. Keep motor power disconnected while programming.

The NodeMCU programs through its USB connector. A bare ESP32-CAM needs a USB-to-UART adapter or ESP32-CAM-MB programmer. For a manual adapter, connect TX/RX crossed, share ground, use **3.3 V UART signals**, power the camera board's **5 V pin** from a suitable supply, hold GPIO0 low during reset to enter upload mode, then remove the GPIO0-ground link and reset to run. Do not rely on a weak adapter's 3.3 V output to power a camera. An MB programmer may handle boot mode automatically.

Read camera startup messages at 115200 baud:

```sh
pio device monitor --port COM5 --baud 115200
```

Each camera prints its IP address. Its endpoints are:

| Endpoint | Front default | Rear default |
| --- | --- | --- |
| MJPEG stream | `http://robot-front.local:81/stream` | `http://robot-rear.local:81/stream` |
| Standalone viewer | `http://robot-front.local/` | `http://robot-rear.local/` |
| Health JSON | `http://robot-front.local/health` | `http://robot-rear.local/health` |

Use the printed IP addresses if `.local` names do not resolve. Reserve those addresses in your router if you want them to stay fixed. Each camera supports **one active video viewer at a time**; close standalone browser viewers before opening the PC controller. Video defaults to **320×240 JPEG**, limited to at most about 10 frames/s per camera; actual frame rate depends on Wi-Fi and capture speed. The streams are independent, not synchronized recordings.

## Pair Bluetooth and start the PC controller

Power the NodeMCU running `motors` and pair **SurveillanceRobot** in the PC's Bluetooth settings, using your configured PIN. Use its **Bluetooth serial port** below, not the USB port used for flashing.

- **Windows:** find the outgoing COM port for SurveillanceRobot under Bluetooth's serial-port settings / Device Manager, for example `COM7`.
- **Linux:** pair and trust it with your Bluetooth manager. Find the SPP channel with `sdptool browse <MAC>`, then bind an RFCOMM device using that channel, for example `sudo rfcomm bind 0 <MAC> <channel>`. Give your user serial-port access as appropriate for the distribution. The app then uses `/dev/rfcomm0`.
- **macOS:** use the paired device's `/dev/cu.*` serial endpoint if the OS exposes one. Some macOS/adapter combinations do not expose Classic SPP; in that case run the controller on a Windows or Linux PC with SPP support.

List serial ports:

```sh
python -m serial.tools.list_ports
```

Start the app, substituting your Bluetooth port and the two camera IP addresses:

```sh
python -m host.controller --port COM7 --front http://192.168.1.101:81/stream --rear http://192.168.1.102:81/stream
```

With working mDNS, `python -m host.controller --port COM7` uses both default camera names. Press **Connect** inside the app to open Bluetooth.

The app uses Tkinter, Pillow and pyserial. On Windows, the official Python installer includes Tkinter when Tcl/Tk is selected. On Debian/Ubuntu install `python3-tk`; Homebrew Python requires its matching `python-tk@<version>` package. `python -m tkinter` should open a test window. Pillow and pyserial are installed by the requirements file.

### Driving

- Hold **W / Up** to drive forward, **S / Down** to reverse, **A / Left** to turn left, and **D / Right** to turn right. Combined forward/turn inputs produce an arc.
- Release the keys or mouse direction button to stop. **Space** or **STOP** clears the current motion.
- Set a speed from `0` to `255`. Start at a low value with the wheels lifted.
- For separate wheel control, enter four signed speeds (`-255` to `255`) and hold **Drive individual wheels**.
- Commands repeat every **100 ms**. Losing window focus, either video for about **2 seconds**, or Bluetooth stops the app's drive intent. Release and press controls again after a stop. Bluetooth reconnection is manual.
- The NodeMCU independently disables its outputs on disconnect, invalid commands, or **600 ms without a complete valid drive command**. It inserts a **75 ms disabled interval before reversing a wheel**. These software intervals do not guarantee the wheel has physically stopped.

`STOP` disables the L298N bridges, so the robot **coasts**. Fit an accessible switch that cuts motor power; software stop is not a mechanical brake. Camera loss is detected by the PC app; a custom Bluetooth client must implement its own video-loss policy.

If a wheel runs backwards, disconnect motor power and swap that motor's leads, or change its `motorPolarity` entry to `-1` in `robot_config.h` and reflash the motor controller.

## Bluetooth protocol

See **[the command protocol](docs/protocol.md)** to use a different Bluetooth client. All commands end with a newline. The wheel order is always **front-left, front-right, rear-left, rear-right**:

```text
M 120 120 120 120
M -100 100 -100 100
M 50 -60 70 -80
STOP
```

## Checks and first hardware test

```sh
python -m unittest discover -s tests -v
c++ -std=c++11 -Wall -Wextra -Werror -Ifirmware/include tests/test_drive.cpp -o /tmp/robot-drive-tests
/tmp/robot-drive-tests
pio run
```

The automated tests cover packet validation, separate wheel speeds, partial/overlong commands, disconnect and timeout behavior, direction-change delays, clock rollover, hold-to-drive stops, multipart JPEG framing, and concurrent HTTP feeds with reconnects. GitHub Actions runs those tests and builds all three targets. Host tests use simulated camera responses; they do not establish physical camera, radio or driver operation.

For the first hardware run, lift the wheels and leave motor power off while checking both feeds. Connect Bluetooth and confirm the controller remains idle. Enable motor power, briefly test one wheel at a time at low speed, then verify release-to-stop, Space, Bluetooth disconnect, camera loss, and NodeMCU reset. Monitor supply voltage, driver temperature and current before a ground test. Hardware testing must be done on the actual robot; none is implied by a successful firmware build.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Camera init fails | AI-Thinker pin map, camera ribbon seating/orientation, stable 5 V supply |
| Camera keeps resetting / brownout | Supply current capacity, cable voltage drop, motor electrical noise, shared ground |
| `.local` does not resolve | Use the IP printed on serial; check mDNS support and network isolation |
| Videos connect one at a time | Close other viewers; each board serves one active stream |
| No video on PC | Same LAN, 2.4 GHz camera access, no AP client isolation, ports 80/81 reachable |
| Motors do not move | Both videos live in app, Bluetooth outgoing port, EN jumpers removed, EN wiring, motor/logic power and ground |
| Motors run backwards | Correct leads or `motorPolarity`; do not change the wheel order |
| No Bluetooth serial endpoint | Original ESP32 target, paired Classic SPP service, OS/adapter support |

Use the video endpoints on a trusted local network. They have no HTTP login or encryption and should not be forwarded to the public internet.
