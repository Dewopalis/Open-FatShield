import os
from pathlib import Path
import subprocess
import tempfile
import unittest

DRIVER = Path(__file__).resolve().parents[1] / "driver"


class TouchpadTest(unittest.TestCase):
    def test_actual_touchpad_transform(self):
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16;
#define clamp(x,lo,hi) ((x)<(lo)?(lo):((x)>(hi)?(hi):(x)))
static void put_unaligned_le16(u16 v,u8 *p) {p[0]=v;p[1]=v>>8;}
#include "ozshield.h"
static int16_t axis(const u8 *p) {return (int16_t)(p[0]|p[1]<<8);}
int main(void) {
    struct oz_shield_touchpad state={0};
    /* Actual captured positions 121,83 -> 122,83: no first-touch jump. */
    u8 first[]={2,8,0x79,0,0x53,0};
    oz_shield_touchpad_report(&state,first,6);
    assert(first[1]==0 && axis(first+2)==0 && axis(first+4)==0);
    u8 move[]={2,8,0x7a,0,0x53,0};
    oz_shield_touchpad_report(&state,move,6);
    assert(axis(move+2)==1 && axis(move+4)==0);
    u8 back[]={2,9,0x78,0,0x50,0};
    oz_shield_touchpad_report(&state,back,6);
    assert(back[1]==1 && axis(back+2)==-2 && axis(back+4)==-3);
    u8 release[]={2,0,0,0,0,0};
    oz_shield_touchpad_report(&state,release,6);
    assert(!state.touched && axis(release+2)==0 && axis(release+4)==0);
    u8 retouch[]={2,8,250,0,250,0};
    oz_shield_touchpad_report(&state,retouch,6);
    assert(axis(retouch+2)==0 && axis(retouch+4)==0);
    u8 jump[]={2,8,0,0,0,0};
    oz_shield_touchpad_report(&state,jump,6);
    assert(axis(jump+2)==-127 && axis(jump+4)==-127);
    u8 gamepad[]={1,8,100,0,100,0}, saved[6];memcpy(saved,gamepad,6);
    oz_shield_touchpad_report(&state,gamepad,6);assert(!memcmp(saved,gamepad,6));
    u8 truncated[]={2,8,1};
    oz_shield_touchpad_report(&state,truncated,3);assert(truncated[1]==8);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "touch.c").write_text(source)
            subprocess.run(["cc", "-g", "-fsanitize=address,undefined", "-I", str(DRIVER),
                            str(path / "touch.c"), "-o", str(path / "touch")], check=True)
            subprocess.run([str(path / "touch")], check=True, timeout=10,
                           env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})


if __name__ == "__main__":
    unittest.main()
