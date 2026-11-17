# Bluetooth motor protocol

The NodeMCU advertises the Bluetooth Classic SPP name **SurveillanceRobot**. Pair using the PIN in `secrets.h`, then open its OS-provided serial endpoint. The PC app opens the endpoint at 115200 baud; Bluetooth transports a byte stream, so this baud setting does not set a radio bitrate.

Commands are ASCII lines terminated by `\n`; `\r\n` is also accepted. There are no acknowledgement messages, so an open PC serial port only confirms the transport is open. Startup diagnostics go to the NodeMCU's USB serial port.

## Set all four motors

```text
M <front-left> <front-right> <rear-left> <rear-right>\n
```

Each value is a signed decimal integer in `[-255, 255]`. Positive is forward according to each wheel's configured polarity, negative is reverse, and zero disables that bridge. Values control PWM duty cycle, not measured RPM. All four speeds update as one command; a malformed value rejects the entire command and stops every motor.

Examples:

| Intent | Packet |
| --- | --- |
| Forward | `M 120 120 120 120\n` |
| Reverse | `M -120 -120 -120 -120\n` |
| Pivot left | `M -120 120 -120 120\n` |
| Pivot right | `M 120 -120 120 -120\n` |
| Test front left only | `M 80 0 0 0\n` |
| Independent values | `M 50 -60 70 -80\n` |

## Stop

```text
STOP\n
```

This immediately clears the requested speeds when processed. Output enables go low on the motor task's next application, normally within about 5 ms. Motors coast rather than actively brake. `M 0 0 0 0\n` also requests zero output.

## Timing and framing

- Repeat the current `M` command every **100 ms** while driving. A complete valid `M` command renews the **600 ms** command deadline. Partial lines and unrelated bytes do not renew it.
- Missing the deadline stops all motors. Unsigned clock arithmetic handles the ESP32's `millis()` rollover.
- Bluetooth disconnect clears speeds and partial commands. Connection changes discard buffered input so a previous session cannot resume motion.
- A line may contain at most **63 bytes before its newline**. Overflow, NUL bytes, disallowed control bytes, missing/extra values, out-of-range integers and unknown commands stop all motors. An overlong line is discarded through its terminating newline before accepting another command.
- When a drive deadline expires during a partial line, the rest of that line is discarded. Send a fresh complete line to drive again.
- Partial lines also expire 600 ms after their first byte when the robot is idle; old fragments cannot later complete a movement command.
- A wheel must stay disabled for **75 ms** before switching polarity, including a reversal after `STOP`. Other wheels retain their own independent state. This dwell does not establish a safe physical stopping time for every load.

The motor firmware has no dependency on camera availability or Wi-Fi. The supplied PC app enforces video availability by clearing drive intent and sending `STOP` when either feed becomes stale. A different Bluetooth client must supply its own deadman and video-loss handling.
