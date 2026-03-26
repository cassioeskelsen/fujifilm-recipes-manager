"""
Write operations for pushing a recipe to a Fujifilm camera over PTP/USB.

Timing requirements (must be respected to avoid camera errors):
  - 50 ms BEFORE each property write
  - 200 ms AFTER each property write
  - A liveness ping AFTER each property write
  Total: ~250 ms per property (14 props × 250 ms ≈ 3.5 s for a full recipe)

On transport failures (CameraConnectionError) the write is retried up to
_WRITE_MAX_RETRIES times with exponential back-off.  A camera.ptp_write.failed
event is published on every failed attempt; camera.ptp_write.succeeded is
published when a write completes successfully.
"""

from __future__ import annotations

import logging
import time

from src.data.camera import constants
from src.domain.camera import events
from src.domain.camera.ptp_device import CameraConnectionError, PTPDevice
from src.domain.camera.queries import recipe_to_ptp_values
from src.domain.images.dataclasses import RECIPE_NAME_MAX_LEN, FujifilmRecipeData

logger = logging.getLogger(__name__)

_PRE_WRITE_DELAY_S = 0.050    # 50 ms before each write
_POST_WRITE_DELAY_S = 0.200   # 200 ms after each write
_WRITE_MAX_RETRIES = 3        # attempts per property before giving up
_WRITE_RETRY_BACKOFF_S = 0.3  # base back-off; doubles each attempt (0.3 s, 0.6 s, 1.2 s)


def push_recipe(
    device: PTPDevice,
    recipe: FujifilmRecipeData,
    *,
    slot_index: int,
    slot_name: str = "",
) -> list[int]:
    """
    Push a film simulation recipe to a custom C-slot on the connected camera.

    Args:
        device:      A connected PTPDevice instance.
        recipe:      The recipe to write.
        slot_index:  1-based custom slot number (e.g. 1 for C1).
        slot_name:   Desired display name for the slot.  If empty, the
                     existing slot name is preserved.

    Returns:
        A list of PTP property codes for which the write failed.  An empty
        list means all writes succeeded.

    Raises:
        CameraConnectionError: If the camera becomes unreachable during the
                               write sequence (mid-write abort).
    """
    if slot_name and (len(slot_name) > RECIPE_NAME_MAX_LEN or not slot_name.isascii()):
        raise ValueError(
            f"slot_name must be ≤{RECIPE_NAME_MAX_LEN} ASCII characters, got {slot_name!r}"
        )

    # --- Phase 1: set slot cursor ---
    rc = device.set_property_uint16(constants.PROP_SLOT_CURSOR, slot_index)
    if rc != 0:
        raise CameraConnectionError(
            f"Failed to set slot cursor to slot {slot_index} (rc={rc})"
        )

    time.sleep(_PRE_WRITE_DELAY_S)

    # --- Phase 2: rename slot if a name was requested ---
    if slot_name:
        current_name = device.get_property_string(constants.PROP_SLOT_NAME)
        if current_name != slot_name:
            device.set_property_string(constants.PROP_SLOT_NAME, slot_name)

    # --- Phase 3: write each property in the recipe map ---
    ptp_items = recipe_to_ptp_values(recipe).items()
    failed_codes: list[int] = [code for code, _ in ptp_items]  # shrinks as writes succeed
    written: list[tuple[int, int]] = []  # (code, value) pairs that reported success

    for code, value in ptp_items:
        time.sleep(_PRE_WRITE_DELAY_S)   # 50 ms before write

        rc = _set_prop_with_retry(device, code, value)
        if rc == 0:
            failed_codes.remove(code)
            written.append((code, value))

        time.sleep(_POST_WRITE_DELAY_S)  # 200 ms after write

        # Liveness ping after every write — abort if camera is gone.
        ping_rc = device.ping()
        if ping_rc != 0:
            raise CameraConnectionError(
                f"Camera became unreachable after writing property 0x{code:04X} "
                f"(ping returned {ping_rc}).  "
                f"Remaining failed codes: {[hex(c) for c in failed_codes]}"
            )

    # --- Phase 4: verify written properties ---
    if slot_name:
        verified_name = device.get_property_string(constants.PROP_SLOT_NAME)
        if verified_name != slot_name:
            logger.warning(
                "Slot name verification failed: wrote %r, read back %r",
                slot_name,
                verified_name,
            )

    verification_failures = _verify_written_properties(device, written)
    failed_codes.extend(verification_failures)

    return failed_codes


def _set_prop_with_retry(device: PTPDevice, code: int, value: int) -> int:
    """
    Write a single property, retrying on transport failures with exponential back-off.

    Publishes camera.ptp_write.failed for every failed attempt and
    camera.ptp_write.succeeded when the write completes successfully.

    Camera rejections (non-zero return code) are published as a single
    camera.ptp_write.failed event and returned immediately without retry,
    because the camera has actively declined the write.

    Returns:
        0 on success, non-zero on failure (transport exhausted or camera rejected).
    """
    last_error: CameraConnectionError | None = None
    prop_hex = f"0x{code:04X}"

    for attempt in range(1, _WRITE_MAX_RETRIES + 1):
        if attempt > 1:
            time.sleep(_WRITE_RETRY_BACKOFF_S * (2 ** (attempt - 2)))

        try:
            rc = device.set_property_int(code, value)
        except CameraConnectionError as exc:
            last_error = exc
            events.publish_event(
                event_type=events.PTP_WRITE_FAILED,
                params={
                    "description": (
                        f"{prop_hex} = {value}: {exc} "
                        f"(attempt {attempt}/{_WRITE_MAX_RETRIES})"
                    )
                },
            )
            continue

        if rc != 0:
            events.publish_event(
                event_type=events.PTP_WRITE_FAILED,
                params={
                    "description": (
                        f"{prop_hex} = {value}: camera rejected write (rc={rc:#x})"
                    )
                },
            )
            return rc

        events.publish_event(
            event_type=events.PTP_WRITE_SUCCEEDED,
            params={"description": f"{prop_hex} = {value}"},
        )
        return 0

    # All retries exhausted due to transport failure; already published per-attempt events.
    assert last_error is not None
    return -1


def _verify_written_properties(
    device: PTPDevice,
    written: list[tuple[int, int]],
) -> list[int]:
    """Read back each successfully written property and check its value.

    Returns a list of PTP codes where the read-back value did not match.
    """
    mismatched: list[int] = []
    for code, expected in written:
        try:
            actual = device.get_property_int(code)
            # Compare lower 32 bits — handles signed/unsigned differences.
            if (actual & 0xFFFFFFFF) != (expected & 0xFFFFFFFF):
                logger.warning(
                    "Verification failed for 0x%04X: wrote %d, read back %d",
                    code,
                    expected,
                    actual,
                )
                mismatched.append(code)
        except CameraConnectionError:
            logger.warning(
                "Verification read failed for 0x%04X (camera error)", code
            )
            mismatched.append(code)
    return mismatched
