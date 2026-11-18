"""Start the app: python -m desk"""

import os
import socket
import threading

import uvicorn

from desk import llm


def _lan_address() -> str | None:
    """The laptop's address on the local network, so a phone on the same Wi-Fi can open the app."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; this only picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    lan = _lan_address()
    print(f"\nStrayline Desk\n  on this laptop:  http://localhost:{port}")
    if lan:
        print(f"  on your phone:   http://{lan}:{port}  (same Wi-Fi or hotspot)")
    print("  loading both models in the background so the first question is fast…\n")
    threading.Thread(target=llm.warm_up, daemon=True).start()
    uvicorn.run("desk.server:app", host="0.0.0.0", port=port)
