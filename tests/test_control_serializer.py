"""Compile the actual control serializer against the real wire structures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "driver"


class SerializerTest(unittest.TestCase):
    def test_wire_layout_and_payload_limits(self):
        source = (DRIVER / "ozusbsvc1.c").read_text()
        start = source.index("static int oz_usb_vendor_class_req(")
        end = source.index("\n}", start) + 2
        harness = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stddef.h>
#include <errno.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint16_t __le16;
#define __packed __attribute__((packed))
#include "ozprotocol.h"
#define OZ_MAX_ELT_PAYLOAD 255
#define put_unaligned(v,p) memcpy((p), &(v), sizeof(v))
struct oz_elt_buf { int unused; };
struct oz_pd { struct oz_elt_buf elt_buff; };
struct oz_usb_ctx { struct oz_pd *pd; };
struct oz_elt_info { unsigned char data[sizeof(struct oz_elt)+OZ_MAX_ELT_PAYLOAD]; };
static unsigned allocations;
static unsigned char captured[257];
static struct oz_elt_info *oz_elt_info_alloc(struct oz_elt_buf *b) {
    allocations++; return calloc(1,sizeof(struct oz_elt_info));
}
static int oz_usb_submit_elt(struct oz_elt_buf *b,struct oz_elt_info *ei,
                           struct oz_usb_ctx *u,int ep,int isoc) {
    memcpy(captured,ei->data,sizeof(captured));free(ei);return 0;
}
'''
        cases = r'''
int main(void) {
    struct oz_pd pd; struct oz_usb_ctx context={.pd=&pd};
    u8 payload[245];memset(payload,0x5a,sizeof(payload));payload[0]=4;
    assert(sizeof(struct oz_vendor_class_req)==10);
    assert(offsetof(struct oz_vendor_class_req,data)==10);
    assert(!oz_usb_vendor_class_req(&context,15,0x21,9,0x0204,0,payload,32));
    struct oz_elt *elt=(struct oz_elt *)captured;
    struct oz_vendor_class_req *body=(struct oz_vendor_class_req *)(elt+1);
    assert(elt->length==42 && body->type==7 && body->req_id==15);
    assert(body->req_type==0x21 && body->request==9 && body->value==0x0204);
    assert(!memcmp(body->data,payload,32));
    assert(!oz_usb_vendor_class_req(&context,1,0x21,9,0,0,payload,245));
    assert(((struct oz_elt *)captured)->length==255);
    unsigned before=allocations;
    assert(oz_usb_vendor_class_req(&context,1,0x21,9,0,0,payload,246)==-EMSGSIZE);
    assert(oz_usb_vendor_class_req(&context,1,0x21,9,0,0,payload,-1)==-EMSGSIZE);
    assert(allocations==before);
    assert(!oz_usb_vendor_class_req(&context,1,0x21,10,0,0,NULL,0));
    assert(((struct oz_elt *)captured)->length==10);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "test.c").write_text(harness + source[start:end] + cases)
            subprocess.run(["cc", "-g", "-fsanitize=address,undefined", "-fstrict-flex-arrays=3",
                            "-I", str(DRIVER), str(path / "test.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True, timeout=10,
                           env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})


if __name__ == "__main__":
    unittest.main()
