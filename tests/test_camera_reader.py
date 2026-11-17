"""Exercise the actual HTTP camera worker without cameras, Bluetooth, or a display."""
import http.server
import threading
import unittest

from host.controller import CameraReader


class CameraReaderTests(unittest.TestCase):
    def test_two_feeds_arrive_independently_and_recover_after_http_failure(self):
        stop = threading.Event()
        counts = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                counts[self.path] = counts.get(self.path, 0) + 1
                if self.path == "/front" and counts[self.path] == 1:
                    self.send_error(503, "Camera restarting")
                    return
                jpeg = b"\xff\xd8" + self.path.encode() + b"\xff\xd9"
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace;boundary=robotframe")
                self.end_headers()
                self.wfile.write(b"\r\n--robotframe\r\nContent-Length: " +
                                 str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg)
                self.wfile.flush()
                stop.wait(5)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        front, rear = [CameraReader(url + path, stop) for path in ("/front", "/rear")]
        try:
            front.start()
            rear.start()
            self.assertIsNotNone(front.latest.get(timeout=3)[2])
            timestamp, jpeg, error = rear.latest.get(timeout=3)
            self.assertIsNone(error)
            self.assertGreater(timestamp, 0)
            self.assertEqual(jpeg, b"\xff\xd8/rear\xff\xd9")
            timestamp, jpeg, error = front.latest.get(timeout=3)
            self.assertIsNone(error)
            self.assertEqual(jpeg, b"\xff\xd8/front\xff\xd9")
            self.assertEqual(counts["/front"], 2)
        finally:
            stop.set()
            server.shutdown()
            server.server_close()
            front.join(timeout=4)
            rear.join(timeout=4)
        self.assertFalse(front.is_alive())
        self.assertFalse(rear.is_alive())
