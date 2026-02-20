"""Flipper Zero serial communication module.

Handles all communication with the Flipper Zero over its CLI serial interface
using raw file descriptors and termios (no pyserial dependency). The Flipper CLI
accepts commands at 230400 baud and responds with text output terminated by a
">: " prompt.

Usage:
    from flipper_serial import FlipperSerial

    with FlipperSerial() as flipper:
        response = flipper.send_command("device_info")
        print(response)

    # Or without context manager:
    flipper = FlipperSerial()
    response = flipper.send_command("device_info")
    flipper.close()
"""

import glob
import os
import select
import time
import termios


# Maximum chunk size for storage write_chunk (Flipper protocol limit)
WRITE_CHUNK_MAX = 512

# Inter-command delay in seconds to avoid overwhelming the CLI parser
COMMAND_DELAY = 0.05

# Default read timeout in deciseconds (for termios VTIME: 1 unit = 100ms)
READ_TIMEOUT_DS = 20  # 2 seconds

# Prompt that terminates every Flipper CLI response
CLI_PROMPT = ">: "
CLI_PROMPT_BYTES = b">: "


def detect_flipper_port():
    """Auto-detect a connected Flipper Zero serial port.

    Searches for /dev/cu.usbmodemflip_* on macOS. Returns the first match,
    or raises FileNotFoundError if no Flipper is found.

    Returns:
        str: The serial port path (e.g., '/dev/cu.usbmodemflip_Mazincea1').

    Raises:
        FileNotFoundError: If no matching serial port is found.
    """
    ports = sorted(glob.glob("/dev/cu.usbmodemflip_*"))
    if not ports:
        raise FileNotFoundError(
            "No Flipper Zero serial port found. "
            "Expected /dev/cu.usbmodemflip_* — is the Flipper connected via USB?"
        )
    if len(ports) > 1:
        print(f"[flipper_serial] Multiple Flipper ports found: {ports}")
        print(f"[flipper_serial] Using: {ports[0]}")
    return ports[0]


class FlipperSerial:
    """Serial communication interface to a Flipper Zero over its USB CLI.

    Uses raw file descriptors with termios for serial I/O at 230400 baud.
    The Flipper CLI echoes commands, uses \\r\\n line endings, and terminates
    each response with a ">: " prompt.

    Can be used as a context manager:
        with FlipperSerial("/dev/cu.usbmodemflip_Mazincea1") as f:
            print(f.send_command("device_info"))
    """

    def __init__(self, port=None):
        """Open a serial connection to the Flipper Zero.

        Args:
            port: Serial port path. If None, auto-detects via
                  /dev/cu.usbmodemflip_* glob.

        Raises:
            FileNotFoundError: If port is None and auto-detection fails.
            OSError: If the serial port cannot be opened.
        """
        if port is None:
            port = detect_flipper_port()

        self.port = port
        self.fd = None
        self._open(port)

    def _open(self, port):
        """Open and configure the serial port."""
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY)

        # Configure termios for 230400 baud, 8N1, raw mode
        attrs = termios.tcgetattr(self.fd)
        attrs[4] = termios.B230400  # ispeed
        attrs[5] = termios.B230400  # ospeed
        attrs[0] = 0                # iflag:  no input processing
        attrs[1] = 0                # oflag:  no output processing
        attrs[2] = (               # cflag:  8-bit, enable receiver, ignore modem
            termios.CS8 | termios.CREAD | termios.CLOCAL
        )
        attrs[3] = 0                # lflag:  raw mode (no echo, no canonical)
        attrs[6][termios.VMIN] = 0  # non-blocking: return whatever is available
        attrs[6][termios.VTIME] = READ_TIMEOUT_DS  # read timeout

        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIOFLUSH)

        # Drain the initial banner / any pending data by sending an empty
        # command and reading until we see the prompt.
        self._drain_banner()

    def _drain_banner(self):
        """Consume the Flipper's startup banner and any buffered data.

        On first connect, the Flipper prints a large ASCII art banner and
        welcome message. We send a bare newline to get to a clean prompt,
        then read and discard everything until we see ">: ".

        If the first attempt doesn't yield a prompt, we retry once more
        since the banner can be large and slow to transmit.
        """
        for attempt in range(2):
            # Send a newline to trigger the prompt
            os.write(self.fd, b"\r\n")
            time.sleep(0.5)

            try:
                self._read_until_prompt(timeout=5.0)
                return  # Got the prompt, we're ready
            except TimeoutError:
                if attempt == 0:
                    # First attempt may have only partially consumed the banner.
                    # Flush and try again.
                    termios.tcflush(self.fd, termios.TCIOFLUSH)
                    time.sleep(0.3)
                else:
                    raise TimeoutError(
                        "Could not get a CLI prompt from the Flipper after "
                        "draining the startup banner. Is the Flipper's CLI "
                        "accessible on this port?"
                    )

    def _read_until_prompt(self, timeout=5.0):
        """Read from the serial port until the ">: " prompt is seen.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            bytes: All data read (including the prompt).

        Raises:
            TimeoutError: If the prompt is not received within the timeout.
        """
        data = b""
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            # Use select for more responsive timeout handling
            ready, _, _ = select.select([self.fd], [], [], min(remaining, 0.5))
            if ready:
                chunk = os.read(self.fd, 4096)
                if chunk:
                    data += chunk
                    if CLI_PROMPT_BYTES in data:
                        return data
            else:
                # No data ready — check if we already have the prompt
                if CLI_PROMPT_BYTES in data:
                    return data

        if CLI_PROMPT_BYTES not in data:
            raise TimeoutError(
                f"Timed out waiting for Flipper prompt after {timeout}s. "
                f"Received {len(data)} bytes: {data[-200:]!r}"
            )
        return data

    def send_command(self, cmd, timeout=10.0):
        """Send a command to the Flipper CLI and return the response.

        Sends the command string, reads until the ">: " prompt, strips the
        echoed command and prompt from the output, and returns the clean
        response text.

        Args:
            cmd: Command string to send (without trailing newline).
            timeout: Maximum seconds to wait for response.

        Returns:
            str: The response text with command echo and prompt stripped.

        Raises:
            TimeoutError: If no prompt is received within the timeout.
            OSError: If the serial connection has been closed.
        """
        if self.fd is None:
            raise OSError("Serial connection is closed")

        # Flush any stale data in the input buffer
        termios.tcflush(self.fd, termios.TCIFLUSH)

        # Send the command
        cmd_bytes = f"\r\n{cmd}\r\n".encode("utf-8")
        os.write(self.fd, cmd_bytes)

        # Small delay to let the Flipper process the command
        time.sleep(COMMAND_DELAY)

        # Read the full response
        raw = self._read_until_prompt(timeout=timeout)
        response = raw.decode("utf-8", errors="replace")

        # Strip the echoed command. The Flipper echoes the command back with
        # a preceding prompt and carriage returns. We find the command in the
        # response and take everything after it, then strip the trailing prompt.
        # The response typically looks like:
        #   \r\n>: <cmd>\r\n<output lines>\r\n>:
        lines = response.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        # Find the line that matches the sent command (echo)
        cmd_stripped = cmd.strip()
        output_start = 0
        for i, line in enumerate(lines):
            # The echo line may contain the prompt prefix
            cleaned = line.strip()
            if cleaned.endswith(cmd_stripped) or cleaned == cmd_stripped:
                output_start = i + 1
                break

        # Take lines after the echoed command, strip trailing prompt
        output_lines = lines[output_start:]

        # Remove trailing prompt line(s)
        while output_lines and output_lines[-1].strip() in (">:", ">: ", ""):
            output_lines.pop()

        return "\n".join(output_lines).strip()

    def storage_mkdir(self, path):
        """Create a directory on the Flipper's SD card.

        Sends 'storage mkdir <path>'. Silently succeeds if the directory
        already exists.

        Args:
            path: Absolute path on the Flipper (e.g., '/ext/infrared').

        Returns:
            str: The command response.
        """
        response = self.send_command(f"storage mkdir {path}")
        # "Storage error: already exists" is not a real error for mkdir
        return response

    def storage_stat(self, path):
        """Check if a file or directory exists on the Flipper.

        Args:
            path: Absolute path to check on the Flipper.

        Returns:
            bool: True if the path exists, False otherwise.
        """
        response = self.send_command(f"storage stat {path}")
        # If the path does not exist, the response contains "Storage error"
        # If it exists, we get file/dir info like "Type: Dir" or "Size: 1234"
        return "Storage error" not in response

    def storage_list(self, path):
        """List directory contents on the Flipper's SD card.

        Args:
            path: Absolute directory path on the Flipper.

        Returns:
            list[tuple[str, str]]: List of (name, type) tuples where type is
                'file' or 'dir'. Returns empty list on error.
        """
        response = self.send_command(f"storage list {path}")
        entries = []

        for line in response.split("\n"):
            line = line.strip()
            if not line or "Storage error" in line:
                continue
            # Format: "[D] dirname" for directories, "[F] filename size" for files
            if line.startswith("[D]"):
                name = line[4:].strip()
                if name:
                    entries.append((name, "dir"))
            elif line.startswith("[F]"):
                # "[F] filename 1234" — name may contain spaces, size is last token
                parts = line[4:].strip()
                if parts:
                    # The size is the last whitespace-separated token
                    tokens = parts.rsplit(None, 1)
                    name = tokens[0] if len(tokens) > 1 else parts
                    entries.append((name, "file"))

        return entries

    def storage_write(self, local_path, remote_path):
        """Write a local file to the Flipper's SD card using storage write_chunk.

        Reads the local file and sends it in chunks of up to 512 bytes using
        the Flipper's write_chunk protocol:
          1. Send 'storage write_chunk <path> <size>'
          2. Wait for "Ready" response
          3. Send exactly <size> bytes of raw data
          4. Wait for OK or error
          5. Repeat for remaining data

        Args:
            local_path: Path to the local file to upload.
            remote_path: Absolute path on the Flipper where the file should
                         be written (e.g., '/ext/infrared/Samsung_TV.ir').

        Raises:
            FileNotFoundError: If local_path does not exist.
            RuntimeError: If the Flipper reports an error during write.
            TimeoutError: If communication times out.
        """
        if self.fd is None:
            raise OSError("Serial connection is closed")
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        with open(local_path, "rb") as f:
            file_data = f.read()

        total_size = len(file_data)
        offset = 0
        chunk_num = 0

        while offset < total_size:
            chunk_size = min(WRITE_CHUNK_MAX, total_size - offset)
            chunk_data = file_data[offset : offset + chunk_size]

            # Step 1: Send the write_chunk command
            cmd = f"storage write_chunk {remote_path} {chunk_size}"
            termios.tcflush(self.fd, termios.TCIFLUSH)
            os.write(self.fd, f"\r\n{cmd}\r\n".encode("utf-8"))

            # Step 2: Wait for "Ready" response
            ready_data = b""
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                rlist, _, _ = select.select(
                    [self.fd], [], [], min(remaining, 0.5)
                )
                if rlist:
                    got = os.read(self.fd, 4096)
                    if got:
                        ready_data += got
                        if b"Ready" in ready_data:
                            break

            if b"Ready" not in ready_data:
                # Check if there's an error instead
                text = ready_data.decode("utf-8", errors="replace")
                if "Storage error" in text:
                    raise RuntimeError(
                        f"Flipper storage error writing {remote_path}: {text}"
                    )
                raise TimeoutError(
                    f"Timed out waiting for 'Ready' from Flipper for chunk "
                    f"{chunk_num} of {remote_path}. Got: {ready_data!r}"
                )

            # Step 3: Send the raw chunk data
            os.write(self.fd, chunk_data)

            # Step 4: Wait for OK / prompt / error
            resp_data = b""
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                rlist, _, _ = select.select(
                    [self.fd], [], [], min(remaining, 0.5)
                )
                if rlist:
                    got = os.read(self.fd, 4096)
                    if got:
                        resp_data += got
                        # The Flipper responds with OK then prompt, or an error
                        if CLI_PROMPT_BYTES in resp_data:
                            break

            resp_text = resp_data.decode("utf-8", errors="replace")
            if "Storage error" in resp_text:
                raise RuntimeError(
                    f"Flipper storage error on chunk {chunk_num} of "
                    f"{remote_path}: {resp_text}"
                )

            offset += chunk_size
            chunk_num += 1

            # Inter-chunk delay
            time.sleep(COMMAND_DELAY)

    def close(self):
        """Close the serial connection to the Flipper.

        Safe to call multiple times. After closing, send_command() and other
        methods will raise OSError.
        """
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def __enter__(self):
        """Support use as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection when exiting context manager."""
        self.close()
        return False

    def __del__(self):
        """Ensure the file descriptor is closed on garbage collection."""
        self.close()


if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 60)
    print("Flipper Zero Serial Communication Test")
    print("=" * 60)

    if port:
        print(f"Using port: {port}")
    else:
        print("Auto-detecting Flipper port...")
        try:
            port = detect_flipper_port()
            print(f"Found: {port}")
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    print("\nConnecting...")
    try:
        flipper = FlipperSerial(port)
    except OSError as e:
        print(f"ERROR: Could not open {port}: {e}")
        sys.exit(1)

    print("Connected!\n")

    try:
        # Run device_info and extract firmware version
        print("Running 'device_info'...")
        info = flipper.send_command("device_info", timeout=10.0)

        # Parse firmware version from the output
        firmware_version = None
        firmware_commit = None
        device_name = None

        for line in info.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "firmware_version":
                    firmware_version = value
                elif key == "firmware_commit":
                    firmware_commit = value
                elif key == "hardware_name":
                    device_name = value

        print(f"\n{'Device Name:':<22} {device_name or 'unknown'}")
        print(f"{'Firmware Version:':<22} {firmware_version or 'unknown'}")
        print(f"{'Firmware Commit:':<22} {firmware_commit or 'unknown'}")

        # Also print the full device_info for reference
        print(f"\n--- Full device_info output ({len(info)} chars) ---")
        # Print first 40 lines to avoid flooding the terminal
        lines = info.split("\n")
        for line in lines[:40]:
            print(f"  {line}")
        if len(lines) > 40:
            print(f"  ... ({len(lines) - 40} more lines)")

    except TimeoutError as e:
        print(f"TIMEOUT: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        flipper.close()
        print("\nConnection closed.")

    print("\n" + "=" * 60)
    print("Test complete.")
    print("=" * 60)
