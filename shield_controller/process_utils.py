"""Bounded process waits, including helpers stuck in a kernel system call."""
import os
import subprocess


def bounded_run(args, timeout=15):
    process = subprocess.Popen(args, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               env={**os.environ, "LC_ALL": "C"})
    try:
        output, _ = process.communicate(timeout=timeout)
    except BaseException:
        process.kill()
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            # Do not wait forever for an uninterruptible kernel syscall.
            pass
        raise
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, args, output=output)
    return output.strip()


def stop_owned_process(process, grace=3):
    if process is None or process.poll() is not None:
        return True
    process.terminate()
    try:
        process.wait(timeout=grace)
        return True
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=2)
            return True
        except subprocess.TimeoutExpired:
            print(f"Process {process.pid} did not exit after SIGKILL; continuing network recovery. "
                  "A kernel fault may require a reboot.", flush=True)
            return False
