import io
import unittest

from host.protocol import encode_wheels, mix_keys, read_mjpeg_frame
from host.intent import DriveIntent


class ProtocolTests(unittest.TestCase):
    def test_each_wheel_has_independent_signed_speed(self):
        self.assertEqual(encode_wheels((255, -255, 32, 0)), b"M 255 -255 32 0\n")

    def test_invalid_wheels_cannot_create_a_drive_packet(self):
        for wheels in ((1, 2, 3), (256, 0, 0, 0), (1.5, 0, 0, 0),
                       (True, 0, 0, 0), (0, 0, 0, -256)):
            with self.subTest(wheels=wheels), self.assertRaises(ValueError):
                encode_wheels(wheels)

    def test_tank_steering_and_opposing_keys(self):
        self.assertEqual(mix_keys({"w"}, 150), (150, 150, 150, 150))
        self.assertEqual(mix_keys({"s"}, 150), (-150, -150, -150, -150))
        self.assertEqual(mix_keys({"a"}, 150), (-150, 150, -150, 150))
        self.assertEqual(mix_keys({"d"}, 150), (150, -150, 150, -150))
        self.assertEqual(mix_keys({"w", "d"}, 150), (150, 0, 150, 0))
        self.assertEqual(mix_keys({"w", "s"}, 150), (0, 0, 0, 0))

    def test_reads_exactly_one_part_even_with_partial_network_reads(self):
        jpeg = b"\xff\xd8camera-data\xff\xd9"

        class ShortReads(io.BytesIO):
            def read(self, count=-1):
                return super().read(min(count, 3))

        part = b"\r\n--robotframe\r\nContent-Type: image/jpeg\r\nContent-Length: "
        stream = ShortReads(part + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + part)
        self.assertEqual(read_mjpeg_frame(stream), jpeg)
        self.assertTrue(stream.readline().startswith(b"\r\n"))

    def test_rejects_missing_oversized_truncated_and_non_jpeg_frames(self):
        parts = [b"--robotframe\r\n\r\n",
                 b"--robotframe\r\nContent-Length: 99999999\r\n\r\n",
                 b"--robotframe\r\nContent-Length: 100\r\n\r\nshort",
                 b"--robotframe\r\nContent-Length: 4\r\n\r\nnope",
                 b"--robotframe\r\nContent-Length: -1\r\n\r\n"]
        for part in parts:
            with self.subTest(part=part), self.assertRaises((ValueError, EOFError)):
                read_mjpeg_frame(io.BytesIO(part))


class IntentTests(unittest.TestCase):
    def test_stop_does_not_allow_key_repeat_to_restart_motion(self):
        intent = DriveIntent()
        intent.press("w")
        self.assertEqual(intent.wheels(100, (0, 0, 0, 0)), (100,) * 4)
        intent.halt()
        intent.press("w")
        self.assertEqual(intent.wheels(100, (0, 0, 0, 0)), (0,) * 4)
        intent.release("w")
        intent.press("w")
        self.assertEqual(intent.wheels(100, (0, 0, 0, 0)), (100,) * 4)

    def test_space_cancels_and_blocks_keyboard_and_buttons_until_released(self):
        intent = DriveIntent()
        intent.press("w")
        intent.press("space")
        intent.press("d")
        intent.direction("a")
        intent.start_manual()
        self.assertEqual(intent.wheels(100, (1, 2, 3, 4)), (0,) * 4)
        intent.release("space")
        self.assertEqual(intent.wheels(100, (1, 2, 3, 4)), (0,) * 4)

    def test_manual_drive_is_independent_and_stops_on_release(self):
        intent = DriveIntent()
        intent.start_manual()
        self.assertEqual(intent.wheels(100, (1, -2, 3, -4)), (1, -2, 3, -4))
        intent.halt()
        self.assertEqual(intent.wheels(100, (1, -2, 3, -4)), (0,) * 4)


if __name__ == "__main__":
    unittest.main()
