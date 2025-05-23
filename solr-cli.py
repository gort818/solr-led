import usb.core
import usb.util
import time
import argparse
import colorsys
import sys

VID = 0x044f
PIDS = [0x0422, 0x042a]  # 0422 = right, 042a = left
INTERFACE = 1
ENDPOINT_OUT = 0x02

# Button to LED mapping (including thumb = 0x00)
BUTTON_TO_LED = {
    0: 0x00,    # thumb
    5: 0x11,
    6: 0x10,
    7: 0x12,
    8: 0x13,
    16: 0x08,
    17: 0x07,
    18: 0x09,
    19: 0x0A,
}

# Groups of LEDs by name
GROUPS = {
    "tm_logo": [0x01, 0x02, 0x03],
    "upper_circles": [0x04, 0x05, 0x06, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F],
    "left_buttons": [BUTTON_TO_LED[b] for b in [5, 6, 7, 8]],
    "right_buttons": [BUTTON_TO_LED[b] for b in [17, 16, 19, 18]],
}

def send_led_packet(dev, led_colors):
    thumbstick_colors = {k: v for k, v in led_colors.items() if k == 0x00}
    other_colors = {k: v for k, v in led_colors.items() if k != 0x00}

    for led_id, color in thumbstick_colors.items():
        packet = bytes([0x01, 0x88, 0x81, 0xFF]) + bytes([led_id]) + color
        dev.write(ENDPOINT_OUT, packet, timeout=1000)
        time.sleep(0.01)

    keys = list(other_colors.keys())
    for i in range(0, len(keys), 2):
        batch = {k: other_colors[k] for k in keys[i:i+2]}
        packet = bytes([0x01, 0x08, 0x85, 0xFF])
        for led_id, color in batch.items():
            packet += bytes([led_id]) + color
        dev.write(ENDPOINT_OUT, packet, timeout=1000)
        time.sleep(0.01)

def hex_to_rgb(hex_str):
    if len(hex_str) != 6:
        raise ValueError("Hex color must be 6 characters (e.g. 'FF0000')")
    return bytes.fromhex(hex_str)

def frange(start, stop, step):
    while start <= stop if step > 0 else start >= stop:
        yield start
        start += step

def breathing_effect(dev, leds, base_rgb):
    try:
        while True:
            # Fade up
            for v in frange(0.1, 1.0, 0.05):
                scaled = bytes([int(c * v) for c in base_rgb])
                led_colors = {led: scaled for led in leds}
                send_led_packet(dev, led_colors)
                time.sleep(0.05)
            # Fade down
            for v in frange(1.0, 0.1, -0.05):
                scaled = bytes([int(c * v) for c in base_rgb])
                led_colors = {led: scaled for led in leds}
                send_led_packet(dev, led_colors)
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nBreathing effect stopped by user.")

def rainbow_breathing_effect(dev, leds):
    try:
        hue = 0.0
        while True:
            for v in list(frange(0.1, 1.0, 0.05)) + list(frange(1.0, 0.1, -0.05)):
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, v)
                scaled = bytes([int(r * 255), int(g * 255), int(b * 255)])
                led_colors = {led: scaled for led in leds}
                send_led_packet(dev, led_colors)
                time.sleep(0.05)
                hue += 0.01
                if hue > 1.0:
                    hue = 0.0
    except KeyboardInterrupt:
        print("\nRainbow breathing stopped by user.")

def find_devices():
    devices = {}
    for pid in PIDS:
        dev = usb.core.find(idVendor=VID, idProduct=pid)
        if dev is not None:
            side = "right" if pid == 0x0422 else "left"
            devices[side] = dev
    return devices

def print_list():
    print("Available devices:")
    print("  left  - PID 042A")
    print("  right - PID 0422\n")
    print("Available groups:")
    for g in GROUPS:
        print(f"  {g} - LEDs: {', '.join(f'0x{led:02X}' for led in GROUPS[g])}")
    print("\nAvailable buttons:")
    for btn, led in sorted(BUTTON_TO_LED.items()):
        print(f"  Button {btn} -> LED 0x{led:02X}")
    print("\nUse --device with left or right, and specify either --group or --buttons with colors.")

def main():
    parser = argparse.ArgumentParser(description="Sol-R Flightstick LED controller CLI")
    parser.add_argument('--device', choices=['left', 'right'], help='Device to configure')
    group_mode = parser.add_mutually_exclusive_group()
    group_mode.add_argument('--group', choices=GROUPS.keys(), help='Group of LEDs to set')
    group_mode.add_argument('--buttons', type=str, help='Comma-separated list of button numbers to set (e.g. 5,6,7)')
    parser.add_argument('--list', action='store_true', help='List devices, groups, and buttons')
    parser.add_argument('--breathing', action='store_true', help='Make LEDs breathe (pulse) with fixed color')
    parser.add_argument('--rainbow', action='store_true', help='Make LEDs breathe with rainbow colors')
    parser.add_argument('color', nargs='?', help='Color in RRGGBB hex (required unless --rainbow)')

    args = parser.parse_args()

    if args.list:
        print_list()
        return

    if args.device is None:
        print("Error: --device is required (use --list to see devices).")
        return

    if not args.group and not args.buttons:
        print("Error: Either --group or --buttons must be specified (use --list to see options).")
        return

    if args.breathing and args.rainbow:
        print("Error: --breathing and --rainbow cannot be used together.")
        return

    if (args.breathing or (not args.rainbow)) and not args.color:
        print("Error: Color argument is required (use RRGGBB hex).")
        return

    devices = find_devices()
    if args.device not in devices:
        print(f"Device '{args.device}' not found.")
        return

    dev = devices[args.device]

    if dev.is_kernel_driver_active(INTERFACE):
        try:
            dev.detach_kernel_driver(INTERFACE)
        except usb.core.USBError as e:
            print(f"Could not detach kernel driver: {e}")
            return

    usb.util.claim_interface(dev, INTERFACE)

    # Determine LEDs to set
    if args.group:
        leds_to_set = GROUPS[args.group]
    else:
        try:
            buttons = [int(b.strip()) for b in args.buttons.split(',')]
        except ValueError:
            print("Invalid button numbers in --buttons argument.")
            return
        leds_to_set = []
        for b in buttons:
            if b not in BUTTON_TO_LED:
                print(f"Button {b} is not known.")
                return
            leds_to_set.append(BUTTON_TO_LED[b])

    try:
        if args.rainbow:
            rainbow_breathing_effect(dev, leds_to_set)
        elif args.breathing:
            base_rgb = hex_to_rgb(args.color)
            breathing_effect(dev, leds_to_set, base_rgb)
        else:
            color = hex_to_rgb(args.color)
            led_colors = {led: color for led in leds_to_set}
            send_led_packet(dev, led_colors)
            print("LED colors updated.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        usb.util.release_interface(dev, INTERFACE)
        try:
            dev.attach_kernel_driver(INTERFACE)
        except usb.core.USBError:
            pass

if __name__ == "__main__":
    main()
