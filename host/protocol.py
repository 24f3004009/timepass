"""Hardware-independent wire formats used by the PC controller."""

MAX_FRAME = 1024 * 1024


def encode_wheels(wheels):
    values = tuple(wheels)
    if len(values) != 4 or any(type(v) is not int or not -255 <= v <= 255 for v in values):
        raise ValueError("Supply four integer wheel speeds from -255 to 255")
    return ("M " + " ".join(map(str, values)) + "\n").encode("ascii")


def mix_keys(keys, speed):
    forward = int("w" in keys) - int("s" in keys)
    turn = int("d" in keys) - int("a" in keys)
    left, right = forward + turn, forward - turn
    scale = max(1, abs(left), abs(right))
    left, right = round(left * speed / scale), round(right * speed / scale)
    return left, right, left, right


def read_mjpeg_frame(stream):
    """Read one Content-Length-delimited JPEG; bound every read/allocation."""
    total = 0
    while True:
        line = stream.readline(1025)
        total += len(line)
        if not line:
            raise EOFError("Camera disconnected")
        if len(line) > 1024 or total > 4096:
            raise ValueError("Invalid multipart boundary")
        if line.strip().startswith(b"--"):
            break
    headers = {}
    while True:
        line = stream.readline(1025)
        total += len(line)
        if not line:
            raise EOFError("Truncated camera headers")
        if len(line) > 1024 or total > 4096:
            raise ValueError("Camera headers too large")
        if line in (b"\n", b"\r\n"):
            break
        name, sep, value = line.partition(b":")
        if not sep:
            raise ValueError("Invalid camera header")
        headers[name.strip().lower()] = value.strip()
    try:
        size = int(headers[b"content-length"])
    except (KeyError, ValueError) as exc:
        raise ValueError("Camera did not send Content-Length") from exc
    if not 4 <= size <= MAX_FRAME:
        raise ValueError("Camera frame size out of range")
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise EOFError("Truncated camera JPEG")
        data.extend(chunk)
    if data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        raise ValueError("Camera frame is not a JPEG")
    return bytes(data)
