"""Generate the SVG/PNG/PDF wiring pack. Run from any directory.

Install requirements-docs.txt first. Motor GPIO labels come from robot_config.h.
Coordinates describe logical terminals, never a module's physical header order.
"""
import html
import json
from pathlib import Path
import re

import pypdfium2
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "diagrams"
W, H = 1440, 1000
INK, MUTED, BORDER = "#162c3d", "#526675", "#aabac4"
SIGNAL, PWM, V12, V5, GND = "#246eb0", "#7b43ac", "#ad6200", "#bf3434", "#354b5c"
PALE = "#f4f7fa"


class Sheet:
    def __init__(self, name, title, subtitle, number):
        self.name, self.ops = name, []
        self.rect(0, 0, W, H, fill="#ffffff", stroke="#ffffff", width=0)
        self.text(48, 53, title, 32, bold=True)
        self.text(48, 86, subtitle, 18, color=MUTED)
        self.line([(48, 108), (1392, 108)], BORDER, 1)
        self.text(48, 974, "TIMEPASS / SCHEMATIC TERMINALS, NOT PHYSICAL HEADER POSITIONS", 14, color=MUTED)
        self.text(1392, 974, f"{number:02d} / 03", 14, color=MUTED, anchor="end")

    def rect(self, x, y, w, h, fill=PALE, stroke=BORDER, width=2):
        self.ops.append(("rect", (x, y, w, h, fill, stroke, width)))

    def text(self, x, y, value, size=20, color=INK, bold=False, anchor="start"):
        self.ops.append(("text", (x, y, value, size, color, bold, anchor)))

    def line(self, points, color=SIGNAL, width=3, dashed=False, arrow=False):
        self.ops.append(("line", (points, color, width, dashed)))
        if arrow:
            x, y = points[-1]
            px, py = points[-2]
            dx, dy = x - px, y - py
            scale = (dx * dx + dy * dy) ** .5
            ux, uy = dx / scale, dy / scale
            self.line([(x - ux * 12 - uy * 6, y - uy * 12 + ux * 6),
                       (x, y), (x - ux * 12 + uy * 6, y - uy * 12 - ux * 6)], color, width)

    def circle(self, x, y, radius=4, fill=INK, stroke=INK, width=1):
        self.ops.append(("circle", (x, y, radius, fill, stroke, width)))

    def ground(self, x, y):
        self.line([(x, y), (x, y + 10)], GND, 2)
        for offset, half in ((10, 15), (16, 10), (22, 5)):
            self.line([(x - half, y + offset), (x + half, y + offset)], GND, 2)

    def pulldown(self, x, y, reference):
        self.circle(x, y, 4, PWM, PWM)
        self.line([(x, y), (x, y + 4)], GND, 2)
        self.rect(x - 4, y + 4, 8, 10, "#ffffff", GND, 2)
        self.ground(x, y + 14)
        self.text(x + 20, y + 29, f"{reference} 10k", 16, color=GND)

    def box(self, x, y, w, h, title, lines=()):
        self.rect(x, y, w, h)
        self.text(x + w / 2, y + 38, title, 24, bold=True, anchor="middle")
        for index, value in enumerate(lines):
            self.text(x + w / 2, y + 73 + index * 28, value, 19, anchor="middle", color=MUTED)

    def svg(self):
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{self.name} wiring diagram">']
        for kind, args in self.ops:
            if kind == "rect":
                x, y, w, h, fill, stroke, width = args
                parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
            elif kind == "text":
                x, y, value, size, color, bold, anchor = args
                parts.append(f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{html.escape(value)}</text>')
            elif kind == "line":
                points, color, width, dashed = args
                dash = ' stroke-dasharray="10 8"' if dashed else ''
                points = " ".join(f"{x},{y}" for x, y in points)
                parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{dash}/>')
            elif kind == "circle":
                x, y, r, fill, stroke, width = args
                parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
        return "\n".join(parts) + "\n</svg>\n"

    def pdf(self, doc):
        page_w, page_h = landscape(A3)
        doc.setPageSize((page_w, page_h))
        scale = min((page_w - 32) / W, (page_h - 32) / H)
        doc.saveState()
        doc.translate((page_w - W * scale) / 2, (page_h - H * scale) / 2)
        doc.scale(scale, scale)
        for kind, args in self.ops:
            if kind == "rect":
                x, y, w, h, fill, stroke, width = args
                doc.setFillColor(colors.HexColor(fill))
                doc.setStrokeColor(colors.HexColor(stroke))
                doc.setLineWidth(width)
                doc.rect(x, H - y - h, w, h, fill=1, stroke=bool(width))
            elif kind == "text":
                x, y, value, size, color, bold, anchor = args
                doc.setFillColor(colors.HexColor(color))
                doc.setFont("Helvetica-Bold" if bold else "Helvetica", size)
                draw = {"start": doc.drawString, "end": doc.drawRightString, "middle": doc.drawCentredString}[anchor]
                draw(x, H - y, value)
            elif kind == "line":
                points, color, width, dashed = args
                doc.setStrokeColor(colors.HexColor(color))
                doc.setLineWidth(width)
                doc.setDash([10, 8] if dashed else [])
                path = doc.beginPath()
                path.moveTo(points[0][0], H - points[0][1])
                for x, y in points[1:]:
                    path.lineTo(x, H - y)
                doc.drawPath(path)
                doc.setDash([])
            elif kind == "circle":
                x, y, r, fill, stroke, width = args
                doc.setFillColor(colors.HexColor(fill))
                doc.setStrokeColor(colors.HexColor(stroke))
                doc.setLineWidth(width)
                doc.circle(x, H - y, r, stroke=1, fill=1)
        doc.restoreState()
        doc.showPage()


def motor_map():
    source = (ROOT / "firmware/include/robot_config.h").read_text()
    pins = json.loads(re.search(r"motorPins\[4\]\[2\]\s*=\s*(\{.*?\});", source).group(1).replace("{", "[").replace("}", "]"))
    enables = json.loads(re.search(r"motorEnablePins\[4\]\s*=\s*(\{.*?\});", source).group(1).replace("{", "[").replace("}", "]"))
    assert len(pins) == len(enables) == 4
    assert len({pin for pair in pins for pin in pair} | set(enables)) == 12
    return [{"wheel": name, "driver": i // 2 + 1, "input_pins": pair,
             "enable_gpio": enables[i], "enable": "ENA" if i % 2 == 0 else "ENB",
             "inputs": ["IN1", "IN2"] if i % 2 == 0 else ["IN3", "IN4"],
             "outputs": ["OUT1", "OUT2"] if i % 2 == 0 else ["OUT3", "OUT4"]}
            for i, (name, pair) in enumerate(zip(("Front left", "Front right", "Rear left", "Rear right"), pins))]


def motor_sheet(mapping):
    s = Sheet("motor-wiring", "Motor control: 12 signal wires", "Remove ENA/ENB jumpers on both drivers. GPIO labels are the actual ESP32 GPIO numbers.", 1)
    s.rect(60, 155, 350, 730)
    s.text(235, 190, "NodeMCU ESP32S", 25, bold=True, anchor="middle")
    s.text(235, 217, "Flash target: motors", 18, color=MUTED, anchor="middle")
    for driver, top in ((1, 175), (2, 545)):
        s.rect(740, top, 290, 335)
        s.text(885, top + 32, f"L298N driver {driver}", 24, bold=True, anchor="middle")
    for index, motor in enumerate(mapping):
        group_y = 240 if index < 2 else 610
        y = group_y + (index % 2) * 126
        for j, (pin, terminal) in enumerate(zip(motor["input_pins"] + [motor["enable_gpio"]], motor["inputs"] + [motor["enable"]])):
            row, color = y + j * 42, PWM if j == 2 else SIGNAL
            s.text(387, row + 6, f"GPIO{pin}", 21, anchor="end", bold=True)
            s.line([(410, row), (740, row)], color)
            s.circle(410, row, 4, color, color)
            s.circle(740, row, 4, color, color)
            s.text(754, row + 6, terminal, 20, color=color, bold=True)
            if j == 2:
                s.pulldown(500, row, f"R{index + 1}")
        center_y = y + 30
        s.text(1215, center_y - 61, motor["wheel"], 22, bold=True, anchor="middle")
        s.circle(1215, center_y, 38, "#ffffff", INK, 2)
        s.text(1215, center_y + 8, "M", 28, bold=True, anchor="middle")
        for j, terminal in enumerate(motor["outputs"]):
            row = center_y - 18 + j * 36
            s.text(1016, row + 6, terminal, 18, anchor="end")
            s.line([(1030, row), (1164, row), (1164, center_y + (-10 if j == 0 else 10)), (1178, center_y + (-10 if j == 0 else 10))], INK)
        s.text(1290, center_y + 7, "12 V DC", 18, color=MUTED)
    s.text(387, 866, "GND", 21, anchor="end", bold=True)
    s.line([(410, 860), (465, 860), (465, 870)], GND)
    s.ground(465, 870)
    for y in (490, 860):
        s.text(754, y + 6, "GND", 20, color=GND, bold=True)
        s.line([(740, y), (655, y), (655, y + 8)], GND)
        s.ground(655, y + 8)
    s.text(90, 900, "3.3 V logic; never connect GPIO to 5 V", 17, color=MUTED)
    s.text(48, 925, "Blue = direction  |  Purple = PWM enable  |  R1-R4 = external 10k pulldowns to common GND", 20)
    s.text(48, 951, "Connect NodeMCU GND, both driver GNDs and all four resistor grounds together. Power wiring is separate.", 18, color=MUTED)
    return s


def system_sheet():
    s = Sheet("system-layout", "Robot layout and wireless links", "Three boards in use: two ESP32-CAMs + one NodeMCU ESP32S. Your second NodeMCU is spare.", 2)
    s.box(65, 180, 330, 155, "Front ESP32-CAM", ("Firmware: front", "robot-front.local:81/stream"))
    s.box(65, 430, 330, 155, "Rear ESP32-CAM", ("Firmware: rear", "robot-rear.local:81/stream"))
    s.box(550, 305, 300, 150, "2.4 GHz Wi-Fi", ("Router / compatible hotspot", "Both cameras on same LAN"))
    s.box(1010, 305, 350, 170, "Host PC", ("Python viewer + controller", "Two live videos", "Bluetooth Classic SPP"))
    s.line([(395, 255), (475, 255), (475, 355), (550, 355)], SIGNAL, dashed=True, arrow=True)
    s.line([(395, 505), (475, 505), (475, 405), (550, 405)], SIGNAL, dashed=True, arrow=True)
    s.text(420, 210, "Wi-Fi video", 18, color=SIGNAL)
    s.line([(850, 380), (1010, 380)], SIGNAL, dashed=True, arrow=True)
    s.box(1010, 690, 350, 150, "NodeMCU ESP32S", ("Firmware: motors", "Bluetooth: SurveillanceRobot"))
    s.line([(1185, 475), (1185, 690)], PWM, dashed=True, arrow=True)
    s.text(1210, 560, "Bluetooth", 20, color=PWM)
    s.text(1210, 590, "commands", 20, color=PWM)
    s.box(545, 690, 300, 150, "2 x L298N drivers", ("8 direction + 4 PWM wires", "See sheet 01"))
    s.box(65, 690, 330, 150, "4 independent motors", ("Front left / front right", "Rear left / rear right"))
    s.line([(1010, 765), (845, 765)], SIGNAL, arrow=True)
    s.line([(545, 765), (395, 765)], INK, arrow=True)
    s.text(48, 920, "The camera boards need only power wiring. No camera-to-NodeMCU signal wires are required.", 20)
    s.text(48, 949, "Wi-Fi carries video; Bluetooth carries motor commands. No wired camera-to-NodeMCU data link.", 18, color=MUTED)
    return s


def programming_sheet():
    s = Sheet("camera-programming", "ESP32-CAM programming connections", "Manual USB-to-UART adapter: 3.3 V UART signal levels, independent regulated 5 V board power.", 3)
    s.box(65, 190, 355, 490, "USB-to-UART adapter", ("USB connection to PC", "TXD / RXD at 3.3 V logic"))
    s.box(910, 190, 440, 490, "ESP32-CAM", ("AI-Thinker + OV2640", "Power through the 5V pin"))
    for y, left, right, reverse, color in ((340, "TXD", "U0R / RX / GPIO3", False, SIGNAL),
                                         (425, "RXD", "U0T / TX / GPIO1", True, SIGNAL),
                                         (510, "GND", "GND", False, GND)):
        s.text(395, y + 6, left, 22, anchor="end", bold=True)
        s.text(930, y + 6, right, 22, bold=True)
        points = [(420, y), (910, y)]
        s.line(list(reversed(points)) if reverse else points, color, arrow=color == SIGNAL)
    s.ground(665, 510)
    s.circle(665, 510, 4, GND, GND)
    s.text(395, 600, "VCC / 3V3", 20, anchor="end", color=MUTED)
    s.text(250, 630, "Leave adapter power pin disconnected", 16, anchor="middle", color=MUTED)
    s.text(930, 600, "5V", 22, color=V5, bold=True)
    s.line([(420, 825), (585, 825), (585, 594), (910, 594)], V5, 4)
    s.box(65, 760, 355, 140, "Regulated 5 V supply", ("Use a supply with enough current", "Connect its negative to GND"))
    s.ground(240, 900)
    s.text(930, 650, "GPIO0", 22, bold=True)
    s.line([(910, 644), (800, 644)], GND)
    s.circle(800, 644, 4, "#ffffff", GND, 2)
    s.circle(735, 644, 4, "#ffffff", GND, 2)
    s.line([(800, 644), (745, 624)], GND)
    s.line([(735, 644), (690, 644)], GND)
    s.ground(690, 644)
    s.text(780, 715, "Temporary GPIO0-to-GND link", 18, anchor="middle")
    s.text(780, 744, "Fit for upload + reset. Remove for run + reset.", 17, anchor="middle")
    s.box(805, 795, 545, 110, "NodeMCU programming", ("Use its own USB port. Motor power OFF.", "Disconnect external 5 V to avoid USB back-feed."))
    s.text(48, 946, "An ESP32-CAM-MB programmer may handle boot mode automatically; follow its own power/boot instructions.", 18, color=MUTED)
    return s


def interactive_html(sheets):
    tabs = "".join(f'<button role="tab" aria-selected="{str(i == 0).lower()}" data-index="{i}">{label}</button>'
                   for i, label in enumerate(("Motor signals", "Wireless data", "Programming")))
    figures = "".join(f'<div class="sheet" {"hidden" if i else ""}>{s.svg()}</div>' for i, s in enumerate(sheets))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--background:light-dark(#fff,#10151b);--foreground:light-dark(#152c3c,#e7edf3);--muted:light-dark(#586775,#acbac7);--card:light-dark(#f4f6f8,#1b2530);--border:light-dark(#ccd5de,#3c4d5d);--primary:light-dark(#225f9e,#8cc6ff);--radius:12px;--font-sans:Arial,sans-serif;--font-mono:monospace;color-scheme:light dark}
*{box-sizing:border-box}body{margin:0;color:var(--foreground);font-family:var(--font-sans);font-size:15px;line-height:1.5}button,input{font:inherit}nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}button{color:var(--foreground);background:var(--card);border:1px solid var(--border);border-radius:7px;padding:8px 12px;cursor:pointer}button[aria-selected="true"]{color:var(--primary);border-color:var(--primary);font-weight:bold}.toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}input{width:160px}.viewport{overflow:auto;max-height:700px;border:1px solid var(--border);border-radius:var(--radius);background:var(--card)}.sheet{width:100%;min-width:650px}.sheet[hidden]{display:none}.sheet svg{display:block;width:100%;height:auto}p{margin:12px 0}.note{color:var(--muted)}.notes{background:var(--card);border-radius:var(--radius);padding:16px;margin-top:14px}.notes p{margin:4px 0}strong{font-weight:700}@media(max-width:450px){button{padding:7px 9px;font-size:13px}}
</style>
<nav role="tablist" aria-label="Wiring sheets">''' + tabs + '''</nav>
<div class="toolbar"><label for="zoom">Diagram zoom</label><input id="zoom" type="range" min="100" max="220" step="10" value="100"><output id="amount">100%</output><button id="fit">Fit width</button></div>
<div class="viewport" tabindex="0" aria-label="Scrollable wiring schematic">''' + figures + '''</div>
<div class="notes"><p><strong>Motor drivers:</strong> remove ENA/ENB jumpers; add one 10k pulldown from each enable input to common GND.</p><p><strong>Ground reference:</strong> connect NodeMCU GND, driver 1 GND and driver 2 GND together.</p><p><strong>Camera data:</strong> each ESP32-CAM sends video to the PC over Wi-Fi. There are no data wires between the cameras and NodeMCU.</p></div>
<p class="note">Logical terminals are shown; header order varies by module. Wire by the printed pin labels. Zoom and scroll to read each connection.</p>
<script>
const sheets=[...document.querySelectorAll('.sheet')],tabs=[...document.querySelectorAll('[role=tab]')],zoom=document.getElementById('zoom');
tabs.forEach((tab,i)=>tab.onclick=()=>{tabs.forEach((t,j)=>t.setAttribute('aria-selected',String(i===j)));sheets.forEach((s,j)=>s.hidden=i!==j);document.querySelector('.viewport').scrollTo(0,0)});
function scale(){sheets.forEach(s=>s.style.width=zoom.value+'%');document.getElementById('amount').textContent=zoom.value+'%'}zoom.oninput=scale;document.getElementById('fit').onclick=()=>{zoom.value=100;scale()};
</script></html>'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mapping = motor_map()
    sheets = [motor_sheet(mapping), system_sheet(), programming_sheet()]
    for sheet in sheets:
        (OUT / f"{sheet.name}.svg").write_text(sheet.svg())
    (OUT / "wiring-map.json").write_text(json.dumps(mapping, indent=2) + "\n")
    (OUT / "interactive-wiring.html").write_text(interactive_html(sheets))
    pdf = OUT / "data-wiring-pack.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=landscape(A3), invariant=1)
    doc.setTitle("Four-wheel robot data wiring")
    doc.setAuthor("timepass project")
    for sheet in sheets:
        sheet.pdf(doc)
    doc.save()
    with pypdfium2.PdfDocument(pdf) as rendered:
        assert len(rendered) == 3
        for index, sheet in enumerate(sheets):
            rendered[index].render(scale=1.7).to_pil().save(OUT / f"{sheet.name}.png")
    print(f"Generated three SVG/PNG schematics, three-page PDF and interactive viewer in {OUT}")


if __name__ == "__main__":
    main()
