import usb.core
import usb.util
import time

VID = 0x044f
PIDS = [0x0422, 0x042a]
INTERFACE = 1
ENDPOINT_OUT = 0x02

LED_IDS = {
    0x00: "Thumbstick LED",
    0x01: "TM Logo Bottom",
    0x02: "TM Logo Right",
    0x03: "TM Logo Left",
    0x04: "Upper Circle",
    0x05: "Upper Right Circle",
    0x06: "Right Middle Circle",
    0x07: "Button 17",
    0x08: "Button 16",
    0x09: "Button 18",
    0x0A: "Button 19",
    0x0B: "Bottom Right Circle",
    0x0C: "Bottom Circle",
    0x0D: "Bottom Left Circle",
    0x0E: "Left Center Circle",
    0x0F: "Upper Left Circle",
    0x10: "Button 6",
    0x11: "Button 5",
    0x12: "Button 7",
    0x13: "Button 8"
}

LED_GROUPS = {
    "tm_logo": [0x01, 0x02, 0x03],
    "circle_group": [0x04, 0x05, 0x06, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F],
    "left_buttons": [0x11, 0x10, 0x12, 0x13],   # Buttons 5,6,7,8
    "right_buttons": [0x07, 0x08, 0x0A, 0x09]   # Buttons 17,16,19,18
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
        raise ValueError("Hex color must be 6 characters (e.g. 'ff0000')")
    return bytes.fromhex(hex_str)

def find_devices():
    devices = []
    for pid in PIDS:
        found = usb.core.find(find_all=True, idVendor=VID, idProduct=pid)
        for dev in found:
            devices.append((dev, pid))
    return devices

def select_device(devices):
    pid_labels = {
        0x0422: "Right Stick",
        0x042a: "Left Stick"
    }

    if len(devices) == 1:
        pid = devices[0][1]
        label = pid_labels.get(pid, f"Unknown (PID {pid:04X})")
        print(f"Found one device: {label}")
        return devices[0][0]

    print("Multiple devices found:")
    for i, (dev, pid) in enumerate(devices):
        label = pid_labels.get(pid, f"Unknown (PID {pid:04X})")
        print(f"  [{i}] {label}")

    while True:
        choice = input("Select device number: ").strip()
        if choice.isdigit() and 0 <= int(choice) < len(devices):
            return devices[int(choice)][0]
        print("Invalid choice.")

def main():
    devices = find_devices()
    if not devices:
        raise ValueError("No compatible devices found")

    dev = select_device(devices)

    if dev.is_kernel_driver_active(INTERFACE):
        dev.detach_kernel_driver(INTERFACE)
    usb.util.claim_interface(dev, INTERFACE)

    try:
        print("Available LEDs:")
        for lid, label in LED_IDS.items():
            print(f"  {lid:02X}: {label}")
        print("\nAvailable Groups:")
        for name, ids in LED_GROUPS.items():
            print(f"  {name}: {[f'{i:02X}' for i in ids]}")

        led_colors = {}

        while True:
            user_input = input("\nEnter LED ID (hex like 00) or group name (e.g. tm_logo), or 'done': ").strip().lower()
            if user_input == "done":
                break

            if user_input in LED_GROUPS:
                led_ids = LED_GROUPS[user_input]
            elif all(c in "0123456789abcdef" for c in user_input) and len(user_input) <= 2:
                try:
                    led_id = int(user_input, 16)
                    if led_id not in LED_IDS:
                        print("Unknown LED ID.")
                        continue
                    led_ids = [led_id]
                except ValueError:
                    print("Invalid LED ID format.")
                    continue
            else:
                print("Unknown LED ID or group name.")
                continue

            color_input = input("Enter color (RRGGBB hex, e.g. FF0000 for red): ").strip().lower()
            try:
                color = hex_to_rgb(color_input)
                for lid in led_ids:
                    led_colors[lid] = color
                    print(f"Set LED {lid:02X} to #{color_input.upper()}")
            except ValueError as e:
                print(e)

        if not led_colors:
            print("No LEDs selected. Exiting.")
            return

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
