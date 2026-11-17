#include "drive_control.h"
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

using robot::DriveControl;

static void send(DriveControl &drive, const std::string &line, uint32_t now) {
  for (char c : line) drive.feed(c, now);
  drive.tick(now, true);
}

static void stopped(const DriveControl &drive) {
  for (int value : drive.outputs()) assert(value == 0);
}

int main() {
  DriveControl drive;
  stopped(drive);
  send(drive, "M 100 -200 30 -40\n", 100);
  assert((drive.outputs() == robot::Wheels{{100, -200, 30, -40}}));
  drive.tick(699, true);
  assert(drive.outputs()[0] == 100);
  drive.tick(700, true);
  stopped(drive);

  const char *bad[] = {"M 256 0 0 0\n", "M -256 0 0 0\n",
    "M 1 2 3\n", "M 1 2 3 4 5\n", "M 1 2 3 4x\n",
    "M 1.0 2 3 4\n", "M 99999999999999999999999 0 0 0\n",
    "FORWARD\n", "STOP extra\n", "\n"};
  for (const auto *line : bad) {
    DriveControl instance;
    send(instance, "M 100 100 100 100\n", 1);
    send(instance, line, 2);
    stopped(instance);
  }

  DriveControl framing;
  send(framing, "M 42 42", 0);
  stopped(framing);
  send(framing, " 42 42\r\n", 1);
  assert(framing.outputs()[0] == 42);
  send(framing, std::string(80, 'X'), 2);
  stopped(framing); // Overflow stops immediately, without waiting for newline.
  send(framing, "M 200 200 200 200\n", 3);
  stopped(framing); // Discard remainder of the overlong line.
  send(framing, "M 25 25 25 25\n", 4);
  assert(framing.outputs()[0] == 25);
  const char embeddedNull[] = "M 50 50\0 50 50\n";
  send(framing, std::string(embeddedNull, sizeof(embeddedNull) - 1), 5);
  stopped(framing);

  DriveControl disconnect;
  send(disconnect, "M 100 100 100 100\n", 0);
  disconnect.tick(1, false);
  stopped(disconnect);
  disconnect.tick(2, true);
  stopped(disconnect);

  DriveControl reverse;
  send(reverse, "M 200 200 200 200\n", 0);
  send(reverse, "M -200 -200 -200 -200\n", 10);
  stopped(reverse);
  reverse.tick(84, true);
  stopped(reverse);
  reverse.tick(85, true);
  assert(reverse.outputs()[0] == -200);
  send(reverse, "STOP\n", 86);
  stopped(reverse);
  send(reverse, "M 100 100 100 100\n", 87);
  stopped(reverse); // Explicit STOP must not bypass reversal dwell.
  reverse.tick(161, true);
  assert(reverse.outputs()[0] == 100);

  DriveControl rollover;
  send(rollover, "M 50 50 50 50\n", UINT32_MAX - 100);
  rollover.tick(498, true);
  assert(rollover.outputs()[0] == 50);
  rollover.tick(499, true);
  stopped(rollover);

  DriveControl expiredPartial;
  send(expiredPartial, "M 10 10 10 10\n", 0);
  send(expiredPartial, "M 200 200", 599);
  expiredPartial.tick(600, true);
  send(expiredPartial, " 200 200\n", 601);
  stopped(expiredPartial); // Old fragments cannot re-arm after a timeout.

  DriveControl idlePartial;
  send(idlePartial, "M 200 200", 0);
  idlePartial.tick(600, true);
  send(idlePartial, " 200 200\n", 601);
  stopped(idlePartial); // Partial commands also expire while initially idle.

  std::cout << "Motor protocol, framing, timeout, disconnect, reversal and rollover checks passed\n";
}
