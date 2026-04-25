"""
Network tools — scan local network, ping hosts, check connectivity.
"""

import asyncio
import socket
import platform
import httpx


def register(mcp):

    @mcp.tool()
    async def scan_network() -> str:
        """Scan the local network and return a list of active devices with hostnames."""
        try:
            # socket.gethostbyname(gethostname()) returns 127.0.x.x on many
            # Linux systems (where the hostname maps to loopback in /etc/hosts),
            # which would make the subnet 127.0.0 and the scan useless. Opening a
            # UDP socket to an external address forces the OS to pick the real
            # outbound interface — no packets are actually sent.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.connect(("8.8.8.8", 80))
                    local_ip = probe.getsockname()[0]
                except OSError:
                    local_ip = socket.gethostbyname(socket.gethostname())
            if local_ip.startswith("127."):
                return "Unable to determine a non-loopback network interface, sir."
            subnet = ".".join(local_ip.split(".")[:3])

            sem = asyncio.Semaphore(50)  # max 50 concurrent pings

            async def ping(ip: str) -> str | None:
                async with sem:
                    cmd = ["ping", "-c", "1", "-W", "1", ip] if platform.system() != "Windows" \
                          else ["ping", "-n", "1", "-w", "1000", ip]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await proc.wait()
                    if proc.returncode == 0:
                        try:
                            name = socket.gethostbyaddr(ip)[0]
                        except socket.herror:
                            name = "unknown"
                        return f"{ip} ({name})"
                    return None

            tasks = [ping(f"{subnet}.{i}") for i in range(1, 255)]
            results = await asyncio.gather(*tasks)
            active = [r for r in results if r]

            if not active:
                return "No active devices found on the local network."
            return f"Found {len(active)} devices:\n" + "\n".join(active)
        except Exception as e:
            return f"Network scan failed: {e}"

    @mcp.tool()
    async def ping_host(host: str) -> str:
        """Ping a host and return latency."""
        try:
            cmd = ["ping", "-c", "3", host] if platform.system() != "Windows" \
                  else ["ping", "-n", "3", host]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stdout.decode()
            if proc.returncode == 0:
                for line in output.splitlines():
                    if "avg" in line or "Average" in line:
                        return f"{host} is reachable. {line.strip()}"
                return f"{host} is reachable."
            return f"{host} is unreachable."
        except asyncio.TimeoutError:
            return f"Ping to {host} timed out."
        except Exception as e:
            return f"Ping failed: {e}"

    @mcp.tool()
    async def check_internet() -> str:
        """Check if the system has internet connectivity."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get("https://www.google.com")
                if r.status_code < 400:
                    return "Internet connection is active, sir. All systems online."
        except Exception:
            pass
        return "No internet connection detected, sir."
