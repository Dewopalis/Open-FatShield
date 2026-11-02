"""Exercise the actual driver callback in a userspace ASan/UBSan harness."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DescriptorCallbackTest(unittest.TestCase):
    def test_actual_callback(self):
        source = (ROOT / "driver/ozhcd.c").read_text()
        start = source.index("void oz_hcd_get_desc_cnf(")
        end = source.index("\n}", start) + 2
        callback = source[start:end]
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
struct usb_ctrlrequest { u8 bRequestType; u16 wValue, wIndex; };
struct urb { unsigned transfer_buffer_length, actual_length;
             void *transfer_buffer, *setup_packet; };
struct oz_hcd { void *hcd; };
struct oz_port { struct oz_hcd *ozhcd; void *hpd; };
static struct urb *pending;
static unsigned completions, requests, requested_offset, requested_length;
static int completion_error, enqueue_error, request_error;
#define oz_dbg(...) ((void)0)
#define le16_to_cpu(x) (x)
static struct urb *oz_find_urb_by_id(struct oz_port *p, int ep, u8 id) {
    struct urb *u = pending; pending = NULL; return u;
}
static int oz_enqueue_ep_urb(struct oz_port *p,int ep,int dir,struct urb *u,u8 id) {
    if (!enqueue_error) pending = u; return enqueue_error;
}
static int oz_usb_get_desc_req(void *p,u8 id,u8 type,u8 dt,u8 ix,u16 wi,
                               unsigned offset,unsigned len) {
    requests++; requested_offset = offset; requested_length = len; return request_error;
}
static void oz_dequeue_ep_urb(struct oz_port *p,int ep,int dir,struct urb *u) {pending=NULL;}
static void oz_complete_urb(void *h,struct urb *u,int err) {completions++;completion_error=err;}
'''
        cases = r'''
static struct oz_hcd hcd;
static struct oz_port port = {.ozhcd = &hcd};
static struct usb_ctrlrequest setup;
static struct urb urb;
static void reset(unsigned size) {
    free(urb.transfer_buffer);
    urb = (struct urb){.transfer_buffer_length=size,.transfer_buffer=malloc(size ? size : 1),
                      .setup_packet=&setup};
    pending=&urb;completions=requests=0;completion_error=enqueue_error=request_error=0;
}
int main(void) {
    unsigned char data[255]; memset(data,0xa5,sizeof(data));
    /* Regression: the observed 199-byte descriptor requested into a 9-byte URB. */
    reset(9); oz_hcd_get_desc_cnf(&port,1,0,data,9,0,199);
    assert(completions==1 && completion_error==0 && urb.actual_length==9);
    assert(!memcmp(urb.transfer_buffer,data,9));
    /* Longer-than-requested reply is clipped without overstating completion. */
    reset(9); oz_hcd_get_desc_cnf(&port,1,0,data,199,0,199);
    assert(urb.actual_length==9 && completion_error==0);
    /* Sequential fragments retain the count across a requeued URB. */
    reset(241); oz_hcd_get_desc_cnf(&port,1,0,data,100,0,241);
    assert(!completions && pending==&urb && urb.actual_length==100);
    assert(requested_offset==100 && requested_length==141);
    oz_hcd_get_desc_cnf(&port,1,0,data,141,100,241);
    assert(completions==1 && urb.actual_length==241 && !completion_error);
    /* A short descriptor is reported as short. */
    reset(64); oz_hcd_get_desc_cnf(&port,1,0,data,18,0,18);
    assert(completions==1 && urb.actual_length==18 && !completion_error);
    /* Invalid offsets and no-progress fragments fail without unsigned underflow. */
    reset(9); oz_hcd_get_desc_cnf(&port,1,0,data,9,10,199);
    assert(completions==1 && completion_error==-EPROTO && !urb.actual_length);
    reset(9); oz_hcd_get_desc_cnf(&port,1,0,data,9,1,199);
    assert(completion_error==-EPROTO && !urb.actual_length);
    reset(9); oz_hcd_get_desc_cnf(&port,1,0,data,0,0,199);
    assert(completion_error==-EPROTO && !requests);
    reset(9); oz_hcd_get_desc_cnf(&port,1,1,data,9,0,199);
    assert(completion_error==-EPIPE && !urb.actual_length);
    reset(241); enqueue_error=-1; oz_hcd_get_desc_cnf(&port,1,0,data,100,0,241);
    assert(completion_error==-ENOMEM && urb.actual_length==100);
    reset(241); request_error=-1; oz_hcd_get_desc_cnf(&port,1,0,data,100,0,241);
    assert(completion_error==-ENOMEM && !pending);
    free(urb.transfer_buffer); puts("descriptor regression cases passed");
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cfile = Path(directory) / "callback.c"
            binary = Path(directory) / "callback"
            cfile.write_text(harness + callback + cases)
            subprocess.run(["cc", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            str(cfile), "-o", str(binary)], check=True)
            # LeakSanitizer cannot inspect threads under the execution sandbox's
            # ptrace; retain address and undefined-behavior instrumentation.
            subprocess.run([str(binary)], check=True, timeout=10,
                           env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})


if __name__ == "__main__":
    unittest.main()
