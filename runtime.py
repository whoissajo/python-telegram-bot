# runtime.py
# A lightweight runtime helper for Pyrogram bots.
# Features:
# - Alive status
# - Uptime calculation
# - Hosting machine details (OS, CPU, RAM, Docker, etc.)
# - Register a /status and /restart command in Pyrogram

import time
import platform
import socket
import os
import sys


class BotRuntime:
    def __init__(self, startup_time: float | None = None):
        # Time when the bot started (epoch seconds)
        self.startup_time = startup_time or time.time()

    def _format_timedelta(self, seconds: float) -> str:
        seconds = int(seconds)
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        if minutes or hours:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    def uptime(self) -> str:
        """Return human-readable uptime since startup."""
        return self._format_timedelta(time.time() - self.startup_time)

    def _memory_info(self) -> str:
        """Try to fetch approximate memory information (best effort, cross-platform)."""
        mem_gb = None

        # Linux: read /proc/meminfo
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            parts = line.split()
                            mem_kb = int(parts[1])
                            mem_gb = mem_kb / 1024.0 / 1024.0
                            break
            except Exception:
                pass

        if mem_gb is not None:
            return f"{mem_gb:.1f} GB"

        # Fallback: unknown (avoid failing on non-Linux)
        return "Unknown"

    def _docker_detection(self) -> str:
        """Detect if running inside Docker/Kubernetes (best effort)."""
        try:
            with open("/proc/1/cgroup", "rt") as f:
                for line in f:
                    if "docker" in line or "kubepods" in line:
                        return "Yes"
        except Exception:
            pass

        if os.environ.get("CONTAINERIZED") in ("1", "true", "yes"):
            return "Yes"

        return "No"

    def host_details(self) -> str:
        """Return a multi-line string with hosting machine details."""
        hostname = socket.gethostname()
        system = platform.system()
        release = platform.release()
        version = platform.version()
        arch = platform.machine()
        cpu_cores = os.cpu_count()
        cwd = os.getcwd()

        # User name (best effort)
        user = None
        try:
            user = os.getlogin()
        except Exception:
            try:
                import pwd  # type: ignore
                user = pwd.getpwuid(os.geteuid()).pw_name
            except Exception:
                user = "unknown"

        mem = self._memory_info()
        docker = self._docker_detection()
        py_ver = platform.python_version()

        lines = [
            f"Hostname: {hostname}",
            f"OS: {system} {release} ({version})",
            f"Architecture: {arch}",
            f"CPU cores: {cpu_cores}",
            f"Working dir: {cwd}",
            f"Memory: {mem}",
            f"Running in Docker: {docker}",
            f"User: {user}",
            f"Python: {py_ver}",
        ]
        return "\n".join(lines)

    def status(self) -> str:
        """Return a full status string including uptime and host details."""
        parts = [
            "Bot status: Alive",
            f"Uptime: {self.uptime()}",
            "",
            "Host details:",
            self.host_details(),
        ]
        return "\n".join(parts)


def register_runtime_handlers(app, runtime: BotRuntime):
    """
    Register a /status and /restart command to report bot runtime information.

    Usage in main.py:
        from runtime import BotRuntime, register_runtime_handlers

        app = Client("my_bot", ...)

        rt = BotRuntime()
        register_runtime_handlers(app, rt)

        app.run()
    """
    # Lazy import to avoid hard dependency at import time
    try:
        from pyrogram import filters
    except Exception:
        raise RuntimeError("Pyrogram is not installed. Install pyrogram to use runtime handlers.")

    @app.on_message(filters.command("status"))
    async def _status_handler(client, message):
        # Reply with the runtime status string
        await message.reply_text(runtime.status())

    @app.on_message(filters.command("restart"))
    async def _restart_handler(client, message):
        admin_id = os.getenv("ADMIN_ID")
        if admin_id is None:
            await message.reply_text("Admin ID is not set in environment variables.")
            return

        try:
            admin_id_int = int(admin_id)
        except ValueError:
            await message.reply_text("Admin ID in environment variables is not a valid integer.")
            return

        if message.from_user.id != admin_id_int:
            await message.reply_text("You are not authorized to use this command.")
            return

        # Send a restart notice
        await message.reply_text("🔄 Restarting bot...")

        # Restart by replacing the current process
        os.execv(sys.executable, [sys.executable] + sys.argv)
