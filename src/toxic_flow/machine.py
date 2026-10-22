"""Facts about the machine a run happens on."""

import resource
import sys


def peak_rss_bytes(who: int = resource.RUSAGE_SELF) -> int:
    """Peak resident memory in bytes. ru_maxrss is bytes on macOS but KiB on Linux."""
    raw = resource.getrusage(who).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024
