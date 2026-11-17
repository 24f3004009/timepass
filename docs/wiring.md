# Wiring and power

Use the **two ESP32-CAM boards for cameras** and **one NodeMCU ESP32S for motor control**. The second NodeMCU is spare. Camera signals remain on their own boards; do not wire camera pins to the NodeMCU.

## NodeMCU to L298N

GPIO numbers below are the ESP32 GPIO labels, not physical header positions. Use a classic NodeMCU-32S / ESP32-WROOM board with these pins exposed.

**Remove all four ENA/ENB jumpers before connecting the NodeMCU.** Leaving a jumper fitted can connect a GPIO to 5 V and defeats speed/stop control. ENA/ENB jumpers are different from the driver's `5V-EN` regulator jumper.

| Motor | Driver output | Direction input 1 | NodeMCU GPIO | Direction input 2 | NodeMCU GPIO | Enable input | NodeMCU PWM GPIO |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Front left | Driver 1 OUT1/OUT2 | IN1 | 16 | IN2 | 17 | ENA | 25 |
| Front right | Driver 1 OUT3/OUT4 | IN3 | 18 | IN4 | 19 | ENB | 26 |
| Rear left | Driver 2 OUT1/OUT2 | IN1 | 21 | IN2 | 22 | ENA | 27 |
| Rear right | Driver 2 OUT3/OUT4 | IN3 | 23 | IN4 | 32 | ENB | 33 |

Fit a **10 kΩ pulldown resistor between each of the four enable signals and GND**. These keep the bridges disabled while the NodeMCU boots, resets, or is disconnected. Never substitute internal software pulldowns for these resistors. Direction inputs may also have external pulldowns, but the enable pulldowns are essential.

The NodeMCU uses 3.3 V logic, which meets the original L298N's TTL input-high requirement. It is **not 5 V tolerant**. None of this pin map uses the ESP32's boot-strap pins or flash pins.

One motor connects to each output pair. Positive commands set the first listed input high and the second low; reverse commands swap them. PWM is on ENA/ENB at 15 kHz with 8-bit duty cycle. Zero speed disables EN and sets both inputs low, allowing the motor to coast. Firmware waits 75 ms before energizing a reversed direction, but this cannot measure rotor speed or current.

## Power connections

Use a fused motor supply and an accessible motor-power switch. Size supplies, wiring and fuses for the motors' measured/specified stall currents.

| Connection | Destination |
| --- | --- |
| 12 V motor supply positive, through fuse/switch | Both drivers' motor-supply terminals (`+12V` / `VS`) |
| Motor supply negative | Common GND |
| Regulated 5 V buck output | Both ESP32-CAM **5V** pins and NodeMCU's documented **5V/VIN** input |
| Buck ground | Common GND |
| Both L298N GND terminals | Common GND |
| All ESP32 GND pins | Common GND |
| Driver logic supply | Regulated 5 V, according to the module's regulator-jumper instructions below |

For common L298N modules, **remove `5V-EN`** to disable the onboard regulator before supplying external regulated 5 V to the logic terminal. Confirm this with your module's labeling/documentation: some modules differ. Do not connect an external 5 V source to a terminal that is acting as the onboard regulator's output. Keep the ENA/ENB jumpers removed regardless of this regulator choice.

A regulated 5 V supply rated at least 3 A is a reasonable starting point for the three ESP32 boards and driver logic; verify actual load and voltage at each board. Camera current peaks and motor interference can reset an inadequately supplied system. Do not power the ESP32s from a driver's small onboard regulator. Avoid back-feeding a computer's USB supply when an external 5 V supply is attached; use the board's supported power arrangement or disconnect external power during USB programming.

Run motor current directly between supply and drivers, not through breadboard ground tracks or ESP32 headers. Keep short, substantial power wiring; add supply decoupling near the drivers and camera boards. Suppress brushed-motor noise with appropriate capacitors (commonly 100 nF across each motor's terminals). Check that the L298N modules have their required flyback diodes and heatsinking.

L298N drivers lose several volts under load and dissipate heat. A 12 V motor will receive less than the supply voltage. Check the L298 datasheet and module cooling against **each motor's stall current**; common hobby modules cannot be assumed to deliver their advertised peak current continuously. Use suitably rated drivers if the motors exceed those limits.

## ESP32-CAM connections

The supported AI-Thinker board already connects its OV2640 internally:

| Signal | GPIO |
| --- | --- |
| D0–D7 / Y2–Y9 | 5, 18, 19, 21, 36, 39, 34, 35 |
| XCLK | 0 |
| PCLK | 22 |
| VSYNC / HREF | 25 / 23 |
| SCCB SDA / SCL | 26 / 27 |
| Camera power-down | 32 |

Only 5 V and GND need external wiring for operation. Each camera board sends video directly to the PC over Wi-Fi. Leave GPIO0 disconnected from GND after flashing; holding it low selects the bootloader. The camera flash LED and microSD card are unused.

The camera pin table is a board identity check, not a request to connect these signals to another ESP32. If your camera board differs from AI-Thinker, change the pin map before flashing.
