"""Serve loopback plus separately verified office LAN and Tailscale interfaces."""
import os
import socket
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def listen_addresses():
    addresses = ['127.0.0.1:8000']
    if os.name != 'nt':
        return addresses
    for network, key in (('LAN', 'BILLTRACK_LAN_IP'), ('Tailnet', 'BILLTRACK_TAILSCALE_IP')):
        address = os.getenv(key)
        if not address:
            continue
        try:
            check = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                str(ROOT / 'scripts/configure_network.ps1'), '-Check', '-Network', network,
                '-Address', address], capture_output=True, text=True, timeout=30)
            if check.returncode == 0:
                addresses.append(address + ':8000')
            else:
                print(network + ' access disabled: ' + (check.stderr.strip() or 'firewall check failed'), flush=True)
        except (OSError, subprocess.TimeoutExpired):
            print(network + ' check unavailable; other verified interfaces remain available.', flush=True)
    return addresses


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    (ROOT / 'logs').mkdir(exist_ok=True)
    sys.stdout = (ROOT / 'logs/server.log').open('a', encoding='utf-8', buffering=1)
    sys.stderr = sys.stdout
    from estate_project.wsgi import application
    from waitress import serve
    sockets = [socket.create_server(('127.0.0.1', 8000))]
    try:
        for address in listen_addresses()[1:]:
            try:
                host, port = address.rsplit(':', 1)
                sockets.append(socket.create_server((host, int(port))))
            except OSError:
                print(address + ' unavailable; other listeners remain available.', flush=True)
        print('BillTrack production listeners: ' + ', '.join(str(sock.getsockname()) for sock in sockets), flush=True)
        serve(application, sockets=sockets)
    finally:
        for sock in sockets:
            sock.close()
