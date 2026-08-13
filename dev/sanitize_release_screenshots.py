from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "static" / "ss"
FONT_DIR = Path("C:/Windows/Fonts")

BG = "#10151b"
PANEL = "#171d24"
PANEL_ALT = "#11171e"
BORDER = "#303944"
TEXT = "#f3f5f7"
MUTED = "#aab6c6"
CYAN = "#55c7d9"
GREEN = "#6ede94"
GOLD = "#efbd4d"
RED = "#ef7770"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(FONT_DIR / filename), size)


def label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    *,
    size: int = 12,
    color: str = TEXT,
    bold: bool = False,
) -> None:
    draw.text(xy, value, font=font(size, bold), fill=color)


def box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    *,
    fill: str = PANEL_ALT,
    outline: str = BORDER,
    radius: int = 7,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    value: str,
    *,
    color: str = CYAN,
) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=(y2 - y1) // 2, fill="#143039", outline=color, width=1)
    label(draw, (x1 + 8, y1 + 4), value, size=9, color=color, bold=True)


def sanitize_header(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((742, 12, 801, 46), radius=14, fill="#1b242a", outline="#37434b")
    label(draw, (754, 23), "DEMO", size=8, color=MUTED, bold=True)


def finish(image: Image.Image, filename: str) -> None:
    # The desktop capture contains unused browser canvas to the right. Keep only
    # the application, then upscale for a crisp README presentation.
    image = image.crop((0, 0, 815, 714))
    image = image.resize((1630, 1428), Image.Resampling.LANCZOS)
    image.save(SCREENSHOTS / filename, optimize=True)


def doctrine_management() -> None:
    image = Image.open(SCREENSHOTS / "raw-doctrine-management-release.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    sanitize_header(draw)

    # Replace all live doctrine, fit, plan, and creator identifiers.
    draw.rectangle((226, 352, 792, 714), fill=PANEL)
    box(draw, (229, 353, 421, 426), fill="#12191f", outline="#9e7b2d")
    label(draw, (257, 365), "HIGHEST", size=9, color=GOLD, bold=True)
    label(draw, (257, 383), "Aegis Vanguard", size=13, bold=True)
    label(draw, (257, 405), "Armor Fleet · Core", size=10, color=MUTED)

    label(draw, (443, 367), "Aegis Vanguard", size=16, bold=True)
    label(draw, (443, 391), "Armor Fleet Doctrine", size=11, color=MUTED)
    pill(draw, (443, 416, 514, 438), "HIGHEST", color=GOLD)

    label(draw, (443, 454), "Fittings (3)", size=11, color=MUTED)
    fits = [
        ("Guardian Logistics", "PRIMARY"),
        ("Apocalypse Line Ship", "CORE"),
        ("Eos Command", "SUPPORT"),
    ]
    y = 476
    for name, role in fits:
        box(draw, (529, y, 779, y + 38), fill="#10232a", outline="#2d8290")
        label(draw, (541, y + 6), name, size=11, bold=True)
        label(draw, (541, y + 22), role, size=8, color=CYAN)
        y += 44

    label(draw, (443, 616), "Linked skill plans (2)", size=11, color=MUTED)
    box(draw, (529, 612, 779, 648), fill="#161d24")
    label(draw, (541, 620), "Aegis Vanguard Core Skills", size=10, bold=True)
    box(draw, (529, 655, 779, 691), fill="#161d24")
    label(draw, (541, 663), "Guardian Logistics Qualification", size=10, bold=True)
    label(draw, (443, 695), "Demo data · Created by Demo Operator", size=9, color=MUTED)
    finish(image, "eqm-doctrine-management.png")


def srp_operations() -> None:
    image = Image.open(SCREENSHOTS / "raw-srp-operations-release.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    sanitize_header(draw)

    draw.rectangle((229, 280, 791, 714), fill=PANEL)
    box(draw, (230, 280, 445, 690), fill="#11171e")
    label(draw, (241, 291), "Create SRP Instance", size=14, bold=True)
    label(draw, (241, 324), "Operation name", size=10, color=MUTED)
    box(draw, (241, 341, 434, 374), fill="#0e141a")
    label(draw, (252, 350), "Operation Ember Shield", size=11)
    label(draw, (241, 388), "Starts (EVE time)", size=10, color=MUTED)
    box(draw, (241, 405, 434, 438), fill="#0e141a")
    label(draw, (252, 414), "2026-08-16 19:00", size=11)
    label(draw, (241, 452), "Doctrine", size=10, color=MUTED)
    box(draw, (241, 469, 434, 502), fill="#0e141a")
    label(draw, (252, 478), "Aegis Vanguard", size=11)
    label(draw, (241, 516), "Brief / notes", size=10, color=MUTED)
    box(draw, (241, 533, 434, 604), fill="#0e141a")
    label(draw, (252, 542), "Submit eligible losses from", size=10)
    label(draw, (252, 559), "the armor-fleet deployment.", size=10)
    box(draw, (241, 619, 434, 658), fill="#e8b847", outline="#e8b847")
    label(draw, (282, 630), "Create SRP instance", size=11, color="#15191f", bold=True)

    label(draw, (465, 291), "Current SRP Instances", size=14, bold=True)
    instances = [
        ("Operation Ember Shield", "OPEN", "Aegis Vanguard", "5 requests · 1.42B ISK"),
        ("Northern Watch Patrol", "REVIEW", "Skirmish Wing", "8 requests · 864M ISK"),
        ("Freighter Escort 07", "PAID", "Logistics Support", "3 requests · 391M ISK"),
    ]
    y = 326
    for title, status, doctrine, summary in instances:
        box(draw, (465, y, 779, y + 104), fill="#0f151b")
        label(draw, (478, y + 11), title, size=12, bold=True)
        status_color = GREEN if status == "OPEN" else GOLD if status == "REVIEW" else CYAN
        pill(draw, (690, y + 9, 765, y + 31), status, color=status_color)
        label(draw, (478, y + 38), doctrine, size=10, color=MUTED)
        label(draw, (478, y + 61), summary, size=10)
        label(draw, (478, y + 82), "Copy public submission link", size=9, color=CYAN, bold=True)
        y += 115
    label(draw, (465, 680), "Fictitious operations and reimbursement values", size=9, color=MUTED)
    finish(image, "eqm-srp-operations.png")


def srp_analytics() -> None:
    image = Image.open(SCREENSHOTS / "raw-srp-analytics-release.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    sanitize_header(draw)

    # The filters contain no live identity data. Replace result content with a
    # clearly synthetic aggregate view so the release image demonstrates the UI.
    draw.rectangle((229, 386, 792, 714), fill=PANEL)
    box(draw, (230, 387, 779, 430), fill="#10232a", outline="#2d8290")
    label(draw, (247, 397), "18 evaluated losses (100%)", size=11, color=CYAN, bold=True)
    label(draw, (247, 414), "Demo analytics · no live killmails or identities", size=9, color=MUTED)

    metrics = [
        ("Ships lost", "18"),
        ("Total loss", "4.82B ISK"),
        ("Average / loss", "267.8M ISK"),
        ("Approved", "3.34B ISK"),
    ]
    x = 230
    for title, value in metrics:
        box(draw, (x, 441, x + 129, 504), fill="#0f151b")
        label(draw, (x + 11, 451), title, size=9, color=MUTED)
        label(draw, (x + 11, 472), value, size=13, bold=True)
        x += 140

    box(draw, (230, 518, 501, 698), fill="#0f151b")
    label(draw, (244, 530), "Loss value by day", size=12, bold=True)
    label(draw, (244, 548), "Demo aggregate · ISK", size=9, color=MUTED)
    chart = (249, 572, 484, 680)
    draw.line((chart[0], chart[3], chart[2], chart[3]), fill="#35404a", width=1)
    draw.line((chart[0], chart[1], chart[0], chart[3]), fill="#35404a", width=1)
    points = [(249, 665), (282, 640), (315, 651), (348, 602), (381, 618), (414, 580), (450, 609), (484, 574)]
    draw.line(points, fill=CYAN, width=3, joint="curve")
    for px, py in points:
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=CYAN)

    box(draw, (512, 518, 779, 698), fill="#0f151b")
    label(draw, (526, 530), "Approved by doctrine", size=12, bold=True)
    bars = [
        ("Aegis Vanguard", 0.86, "1.84B"),
        ("Skirmish Wing", 0.58, "984M"),
        ("Logistics Support", 0.31, "516M"),
    ]
    y = 563
    for name, fraction, value in bars:
        label(draw, (526, y), name, size=9)
        label(draw, (731, y), value, size=9, color=MUTED)
        draw.rounded_rectangle((526, y + 17, 755, y + 27), radius=5, fill="#26313a")
        draw.rounded_rectangle((526, y + 17, 526 + int(229 * fraction), y + 27), radius=5, fill=GOLD)
        y += 42
    label(draw, (526, 682), "Synthetic release data", size=9, color=MUTED)
    finish(image, "eqm-srp-analytics.png")


def main() -> None:
    doctrine_management()
    srp_operations()
    srp_analytics()


if __name__ == "__main__":
    main()
