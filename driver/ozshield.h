/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _OZSHIELD_H
#define _OZSHIELD_H

/* Blake report 2 carries absolute finger coordinates, despite its relative
 * HID axes. Match the coordinate/contact interpretation in NVIDIA's original
 * hid-nvidia-blake.c, without introducing pointer acceleration here.
 */
struct oz_shield_touchpad {
	u8 x;
	u8 y;
	bool touched;
};

static inline void oz_shield_touchpad_report(struct oz_shield_touchpad *state,
					   u8 *data, unsigned int size)
{
	bool touched;
	u8 x, y;
	int dx = 0, dy = 0;

	if (size != 6 || data[0] != 2)
		return;
	touched = !!(data[1] & 0x08);
	x = data[2];
	y = data[4];
	if (touched && state->touched) {
		dx = clamp((int)x - state->x, -127, 127);
		dy = clamp((int)y - state->y, -127, 127);
	}
	state->x = x;
	state->y = y;
	state->touched = touched;
	/* Contact is not an extra mouse button; retain physical button bits. */
	data[1] &= ~0x08;
	put_unaligned_le16((u16)dx, data + 2);
	put_unaligned_le16((u16)dy, data + 4);
}

#endif
