#!/bin/sh
set -eu
shield_kernel_version="${1:-$(uname -r)}"
shield_kernel_dir="${2:-/lib/modules/$shield_kernel_version/build}"
if [ ! -r "$shield_kernel_dir/Makefile" ]; then
    echo "Missing kernel headers: $shield_kernel_dir" >&2
    exit 1
fi
if grep -q '^CONFIG_CC_IS_CLANG=y' "$shield_kernel_dir/.config"; then
    exec make -C "$shield_kernel_dir" M="$PWD/driver" CONFIG_USB_WPAN_HCD=m LLVM=1 W=1 modules
else
    exec make -C "$shield_kernel_dir" M="$PWD/driver" CONFIG_USB_WPAN_HCD=m W=1 modules
fi
