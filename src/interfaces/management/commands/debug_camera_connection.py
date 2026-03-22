"""
Django management command: debug_camera_connection

Scans the USB bus for Fujifilm devices and reports what it finds, without
attempting a PTP session.  Use this when camera_info fails with "not found".

Usage:
    python manage.py debug_camera_connection
"""

import usb.core
import usb.util
from django.core.management.base import BaseCommand

_FUJIFILM_VENDOR_ID = 0x04CB


class Command(BaseCommand):
    help = "Scan USB bus for Fujifilm cameras and diagnose connection issues."

    def handle(self, *args, **options):
        self.stdout.write("\nScanning USB bus…\n")

        all_devices = list(usb.core.find(find_all=True))
        self.stdout.write(f"Total USB devices detected: {len(all_devices)}")

        fuji_devices = [d for d in all_devices if d.idVendor == _FUJIFILM_VENDOR_ID]

        if not fuji_devices:
            self.stdout.write(self.style.ERROR(
                "\nNo Fujifilm device found (vendor ID 0x04CB).\n"
            ))
            self.stdout.write("Checklist:")
            self.stdout.write("  1. Camera is powered on and USB cable is connected.")
            self.stdout.write("  2. USB mode is set to RAW CONV. / BACKUP RESTORE")
            self.stdout.write("     (MENU → CONNECTION SETTING → USB SETTING).")
            self.stdout.write("     It must NOT be in USB Mass Storage / card reader mode.")
            self.stdout.write("  3. On Linux: udev rule allows access without sudo.")
            self.stdout.write("     Quick test: sudo python manage.py camera_info")
            self.stdout.write("\nAll detected vendor IDs:")
            vendor_ids = sorted({d.idVendor for d in all_devices})
            for vid in vendor_ids:
                self.stdout.write(f"  0x{vid:04X}")
            return

        self.stdout.write(self.style.SUCCESS(
            f"\nFound {len(fuji_devices)} Fujifilm device(s):\n"
        ))

        for dev in fuji_devices:
            self._print_device(dev)

    def _print_device(self, dev: usb.core.Device) -> None:
        self.stdout.write(
            f"  Vendor:Product  0x{dev.idVendor:04X}:0x{dev.idProduct:04X}"
        )

        try:
            manufacturer = usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else "—"
            product = usb.util.get_string(dev, dev.iProduct) if dev.iProduct else "—"
            self.stdout.write(f"  Manufacturer:   {manufacturer}")
            self.stdout.write(f"  Product:        {product}")
        except usb.core.USBError as e:
            self.stdout.write(self.style.WARNING(
                f"  (Could not read string descriptors: {e} — likely a permissions issue)"
            ))

        # Check if a kernel driver has claimed the interface
        try:
            active = dev.is_kernel_driver_active(0)
            if active:
                self.stdout.write(self.style.WARNING(
                    "  Kernel driver active on interface 0 — "
                    "will be detached automatically on connect()."
                ))
            else:
                self.stdout.write("  No kernel driver on interface 0.")
        except usb.core.USBError as e:
            self.stdout.write(self.style.WARNING(f"  Could not check kernel driver: {e}"))

        # Try to inspect endpoints
        try:
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]
            ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: (
                    usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                    and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
                ),
            )
            ep_in = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: (
                    usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                    and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
                ),
            )
            if ep_out and ep_in:
                self.stdout.write(self.style.SUCCESS(
                    f"  PTP bulk endpoints found: "
                    f"OUT=0x{ep_out.bEndpointAddress:02X}  IN=0x{ep_in.bEndpointAddress:02X}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    "  PTP bulk endpoints NOT found — camera is likely in the wrong USB mode."
                ))
        except usb.core.USBError as e:
            self.stdout.write(self.style.ERROR(
                f"  Could not read USB configuration: {e}\n"
                "  → On Linux run:  sudo python manage.py camera_info\n"
                "    Or add a udev rule — see docs/camera_usb_access.md."
            ))

        self.stdout.write("")
