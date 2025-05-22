import usb.core
import usb.util
import time

VID = 0x044f
PIDS = [0x0422, 0x042a]  # Support both product IDs
INTERFACE = 1
ENDPOINT_OUT = 0x02

# LED IDs and descriptions (including 00 thumbstick)
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

def send_led_packet(dev, led_colors):
    # Separate thumbstick from others
    thumbstick_colors = {k: v for k, v in led_colors.items() if k == 0x00}
    other_colors = {k: v for k, v in led_colors.items() if k != 0x00}

    # Send thumbstick LED packets
    for led_id, color in thumbstick_colors.items():
        # Header for thumbstick LEDs is different: 018881ff
        packet = bytes([0x01, 0x88, 0x81, 0xFF]) + bytes([led_id]) + color
        dev.write(ENDPOINT_OUT, packet, timeout=1000)
        time.sleep(0.01)

    # Send other LEDs packets in pairs (to reduce USB calls)
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

def main():
    dev = None
    for pid in PIDS:
        dev = usb.core.find(idVendor=VID, idProduct=pid)
        if dev is not None:
            print(f"Found device with PID {pid:04X}")
            break

    if dev is None:
        raise ValueError("Device not found with any known PID")

    if dev.is_kernel_driver_active(INTERFACE):
        dev.detach_kernel_driver(INTERFACE)

    usb.util.claim_interface(dev, INTERFACE)

    try:
        print("Available LEDs:")
        for lid, label in LED_IDS.items():
            print(f"  {lid:02X}: {label}")

        led_colors = {}

        while True:
            user_input = input("\nEnter LED ID (hex like 00, or 'done'): ").strip().lower()
            if user_input == "done":
                break

            try:
                led_id = int(user_input, 16)
                if led_id not in LED_IDS:
                    print("Unknown LED ID.")
                    continue
            except ValueError:
                print("Invalid LED ID format.")
                continue

            color_input = input("Enter color (RRGGBB hex, e.g. FF0000 for red): ").strip().lower()
            try:
                color = hex_to_rgb(color_input)
                led_colors[led_id] = color
                print(f"Set LED {led_id:02X} to #{color_input.upper()}")
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
