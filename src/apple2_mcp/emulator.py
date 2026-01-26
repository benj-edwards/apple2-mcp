"""Bobbin emulator process manager.

Uses pexpect to control the Bobbin Apple II emulator interactively.
Provides methods for:
- Starting/stopping the emulator
- Sending keystrokes
- Entering debugger and executing commands
- Reading/writing memory
- Managing snapshots
"""

import os
import re
import time
import shutil
from pathlib import Path
from typing import Optional

import pexpect

from .screen import decode_screen, SCREEN_LINE_ADDRESSES, SCREEN_WIDTH, SCREEN_HEIGHT


class BobbinError(Exception):
    """Error from Bobbin emulator."""
    pass


class Emulator:
    """Manages a Bobbin emulator process."""

    # Debugger prompt pattern
    DEBUGGER_PROMPT = ">"

    # Default Bobbin path (can be overridden)
    DEFAULT_BOBBIN_PATH = None

    def __init__(self, bobbin_path: Optional[str] = None):
        """Initialize emulator manager.

        Args:
            bobbin_path: Path to bobbin executable. If None, searches common locations.
        """
        self.bobbin_path = bobbin_path or self._find_bobbin()
        self.process: Optional[pexpect.spawn] = None
        self.in_debugger = False
        self.machine_type = "enhanced"

    def _find_bobbin(self) -> str:
        """Find the bobbin executable."""
        # Check common locations
        candidates = [
            # Relative to this package (development) - go up from src/apple2_mcp/
            Path(__file__).parent.parent.parent / "bobbin" / "src" / "bobbin",
            # System installed
            Path("/usr/local/bin/bobbin"),
            Path("/opt/homebrew/bin/bobbin"),
            # In PATH
            shutil.which("bobbin"),
        ]

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(Path(candidate).resolve())

        raise BobbinError(
            "Could not find bobbin executable. "
            "Please provide bobbin_path or install bobbin."
        )

    @property
    def is_running(self) -> bool:
        """Check if emulator process is running."""
        return self.process is not None and self.process.isalive()

    def boot(self, machine: str = "enhanced", disk: Optional[str] = None,
             timeout: float = 10.0, uthernet2: bool = False) -> str:
        """Start the emulator and wait for BASIC prompt.

        Args:
            machine: Machine type (plus, enhanced, twoey, original)
            disk: Optional disk image path to load
            uthernet2: Enable Uthernet II network card emulation in slot 3

        Returns:
            Initial screen contents
        """
        if self.is_running:
            self.shutdown()

        self.machine_type = machine

        # Build command
        cmd = [self.bobbin_path, "--simple", "-m", machine]
        if disk:
            cmd.extend(["--disk", disk])
        if uthernet2:
            cmd.append("--uthernet2")

        # Start process
        self.process = pexpect.spawn(
            cmd[0],
            cmd[1:],
            encoding='latin-1',  # Apple II uses high-bit ASCII
            timeout=timeout,
        )

        # Wait for the BASIC prompt (])
        try:
            self.process.expect(r'\]', timeout=timeout)
        except pexpect.TIMEOUT:
            raise BobbinError("Timeout waiting for BASIC prompt")

        # Give emulator a moment to settle and flush any pending output
        time.sleep(0.2)
        try:
            self.process.read_nonblocking(size=65536, timeout=0.1)
        except Exception:
            pass

        self.in_debugger = False
        return self.process.before + "]"

    def shutdown(self):
        """Stop the emulator."""
        if self.process:
            try:
                # Try graceful exit via debugger
                self.enter_debugger()
                self.process.sendline("q")
                self.process.expect(pexpect.EOF, timeout=2)
            except Exception:
                pass
            finally:
                if self.process.isalive():
                    self.process.terminate(force=True)
                self.process = None
                self.in_debugger = False

    def enter_debugger(self, timeout: float = 2.0) -> bool:
        """Enter the Bobbin debugger (Ctrl-C twice).

        Returns:
            True if now in debugger
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        if self.in_debugger:
            # Verify we're actually at a prompt
            try:
                self.process.read_nonblocking(size=65536, timeout=0.05)
            except Exception:
                pass
            self.process.sendline("")
            try:
                self.process.expect(r'\n>', timeout=0.5)
                return True
            except pexpect.TIMEOUT:
                # We thought we were in debugger but aren't
                self.in_debugger = False

        # Aggressively flush any pending output
        for _ in range(3):
            try:
                self.process.read_nonblocking(size=65536, timeout=0.1)
            except Exception:
                pass
            time.sleep(0.05)

        # Try up to 3 times to enter debugger
        for attempt in range(3):
            # Send Ctrl-C twice with delays
            self.process.sendcontrol('c')
            time.sleep(0.1)
            self.process.sendcontrol('c')
            time.sleep(0.2)

            # Wait for debugger prompt (includes register dump ending with >)
            try:
                self.process.expect(r'>', timeout=timeout)
                self.in_debugger = True
                # Verify by sending empty line and waiting for prompt
                time.sleep(0.1)
                try:
                    self.process.read_nonblocking(size=65536, timeout=0.05)
                except Exception:
                    pass
                self.process.sendline("")
                try:
                    self.process.expect(r'\n>', timeout=0.5)
                except pexpect.TIMEOUT:
                    pass  # Continue anyway - first expect succeeded
                return True
            except pexpect.TIMEOUT:
                # Flush and try again
                try:
                    self.process.read_nonblocking(size=65536, timeout=0.1)
                except Exception:
                    pass

        return False

    def sync_debugger(self, timeout: float = 1.0) -> bool:
        """Synchronize debugger state by sending empty command and waiting for prompt.

        This ensures we're at a known state (debugger prompt) before continuing.

        Returns:
            True if synchronized successfully
        """
        if not self.in_debugger:
            return False

        # Flush any pending output
        try:
            self.process.read_nonblocking(size=65536, timeout=0.05)
        except Exception:
            pass

        # Send empty line and wait for prompt on new line
        self.process.sendline("")
        try:
            self.process.expect(r'\n>', timeout=timeout)
            return True
        except pexpect.TIMEOUT:
            return False

    def exit_debugger(self, timeout: float = 2.0) -> bool:
        """Exit debugger and continue emulation.

        Returns:
            True if exited debugger
        """
        if not self.in_debugger:
            return True

        # First sync to make sure we're at a prompt
        self.sync_debugger(timeout=0.5)

        # Flush before sending continue
        try:
            self.process.read_nonblocking(size=65536, timeout=0.05)
        except Exception:
            pass

        self.process.sendline("c")
        self.in_debugger = False

        # Wait for "Continuing..." message
        try:
            self.process.expect(r'Continuing\.\.\.', timeout=0.5)
        except pexpect.TIMEOUT:
            pass

        # Give emulator time to resume and stabilize
        time.sleep(0.3)

        # Aggressively flush any buffered output (multiple attempts)
        for _ in range(3):
            try:
                self.process.read_nonblocking(size=65536, timeout=0.05)
            except Exception:
                pass
            time.sleep(0.05)

        return True

    def debugger_command(self, cmd: str, timeout: float = 2.0,
                         stay_in_debugger: bool = True) -> str:
        """Execute a debugger command and return output.

        Args:
            cmd: Command to execute
            timeout: Timeout for command response
            stay_in_debugger: If True, stay in debugger after command.
                              If False, exit debugger if we entered it.

        Returns:
            Command output
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            if not self.enter_debugger():
                raise BobbinError("Failed to enter debugger")

        self.process.sendline(cmd)

        # Wait for next prompt
        try:
            self.process.expect(r'\n>', timeout=timeout)
            output = self.process.before
        except pexpect.TIMEOUT:
            output = self.process.before if self.process.before else ""

        # Exit debugger if we entered it and caller doesn't want to stay
        if not stay_in_debugger and not was_in_debugger:
            self.exit_debugger()

        return output.strip()

    def peek(self, address: int, count: int = 1) -> list[int]:
        """Read bytes from memory.

        Args:
            address: Starting address (0-65535)
            count: Number of bytes to read

        Returns:
            List of byte values
        """
        if count == 1:
            # Single byte
            output = self.debugger_command(f"{address:04X}", stay_in_debugger=False)
        else:
            # Range
            end_addr = min(address + count - 1, 0xFFFF)
            output = self.debugger_command(f"{address:04X}.{end_addr:04X}", stay_in_debugger=False)

        # Parse hex output
        # Format: "0400: A0 A0 A0 A0 A0 A0 A0 A0"
        bytes_list = []
        for line in output.split('\n'):
            # Extract hex bytes after the colon
            if ':' in line:
                hex_part = line.split(':', 1)[1]
            else:
                hex_part = line

            # Parse hex values
            for token in hex_part.split():
                token = token.strip()
                if re.match(r'^[0-9A-Fa-f]{2}$', token):
                    bytes_list.append(int(token, 16))

        return bytes_list[:count]

    def poke(self, address: int, data: int | list[int] | bytes) -> bool:
        """Write bytes to memory.

        Args:
            address: Starting address
            data: Byte value, list of bytes, or bytes object

        Returns:
            True if successful
        """
        if isinstance(data, int):
            data = [data]
        elif isinstance(data, bytes):
            data = list(data)

        # Chunk large writes to avoid overwhelming pexpect/debugger
        # Each byte becomes "XX " (3 chars), plus address prefix ~7 chars
        # Keep command lines under ~200 bytes for reliability
        CHUNK_SIZE = 64  # bytes per command

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            if not self.enter_debugger():
                raise BobbinError("Failed to enter debugger for poke")

        for offset in range(0, len(data), CHUNK_SIZE):
            chunk = data[offset:offset + CHUNK_SIZE]
            chunk_addr = address + offset
            hex_values = ' '.join(f"{b:02X}" for b in chunk)
            cmd = f"{chunk_addr:04X}: {hex_values}"

            # Flush before sending command
            try:
                self.process.read_nonblocking(size=65536, timeout=0.01)
            except Exception:
                pass

            # Send command and wait for prompt on new line
            self.process.sendline(cmd)
            try:
                # Wait for newline followed by prompt - more specific pattern
                self.process.expect(r'\n>', timeout=2.0)
            except pexpect.TIMEOUT:
                # Try to recover by syncing
                self.sync_debugger(timeout=1.0)

            # Small delay between chunks to avoid overwhelming
            if len(data) > CHUNK_SIZE:
                time.sleep(0.01)

        # Sync to ensure we're at a known state
        self.sync_debugger(timeout=1.0)

        # For large writes, stay in debugger to avoid re-entry issues
        # Only exit if we entered and data was small
        if not was_in_debugger and len(data) <= 64:
            self.exit_debugger()

        return True

    def read_screen_memory(self) -> dict[int, int]:
        """Read the entire text screen memory.

        Returns:
            Dict mapping addresses to byte values
        """
        # Enter debugger once for the whole operation
        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            if not self.enter_debugger():
                raise BobbinError("Failed to enter debugger for screen read")

        memory = {}

        # Read text page 1 ($0400-$07FF) in chunks to avoid huge reads
        for start in range(0x0400, 0x0800, 0x100):
            end_addr = start + 0xFF
            output = self.debugger_command(f"{start:04X}.{end_addr:04X}", stay_in_debugger=True)

            # Parse hex output
            for line in output.split('\n'):
                if ':' in line:
                    hex_part = line.split(':', 1)[1]
                else:
                    hex_part = line

                for token in hex_part.split():
                    token = token.strip()
                    if re.match(r'^[0-9A-Fa-f]{2}$', token):
                        addr = start + len([k for k in memory if k >= start])
                        if addr < 0x0800:
                            memory[addr] = int(token, 16)

        # Exit debugger if we entered it
        if not was_in_debugger:
            self.exit_debugger()

        return memory

    def read_screen(self) -> list[str]:
        """Read the current screen contents as text.

        Returns:
            List of 24 strings, each 40 characters
        """
        memory = self.read_screen_memory()
        return decode_screen(memory)

    def inject_keys(self, text: str, include_return: bool = False) -> None:
        """Inject keystrokes via debugger for reliable AI agent input.

        This method uses Bobbin's keyboard injection queue, which bypasses
        timing issues that can occur with stdin-based input.

        Args:
            text: Text to inject (will be uppercased)
            include_return: Add RETURN at end
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        # Apple II is uppercase
        text = text.upper()

        # Escape special characters for the keys command
        escaped = text.replace('\\', '\\\\')
        if include_return:
            escaped += '\\r'

        # Use debugger command to inject keys
        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            self.enter_debugger()

        self.debugger_command(f"keys {escaped}")

        if not was_in_debugger:
            # Exit debugger and consume output so it doesn't pollute pexpect buffer
            self.process.sendline("c")
            self.in_debugger = False
            # Wait briefly for emulation to start processing keys
            time.sleep(0.05)
            # Consume any debugger output from pexpect buffer
            try:
                self.process.expect(r'Continuing\.\.\.', timeout=0.5)
            except pexpect.TIMEOUT:
                pass

    def type_text(self, text: str, delay: float = 0.02,
                  include_return: bool = False, use_inject: bool = False) -> None:
        """Type text into the emulator.

        Args:
            text: Text to type (will be uppercased)
            delay: Delay between keystrokes (ignored if use_inject=True)
            include_return: Add RETURN at end
            use_inject: Use reliable keyboard injection (recommended for AI agents)
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        # Use reliable injection by default
        if use_inject:
            self.inject_keys(text, include_return)
            return

        # Legacy stdin-based input (may have timing issues)
        if self.in_debugger:
            self.exit_debugger()

        # Apple II is uppercase
        text = text.upper()

        for char in text:
            self.process.send(char)
            if delay > 0:
                time.sleep(delay)

        if include_return:
            self.process.send('\r')

    def send_return(self) -> None:
        """Send RETURN key."""
        if self.in_debugger:
            self.exit_debugger()
        self.process.send('\r')

    def send_control(self, char: str) -> None:
        """Send a control character.

        Args:
            char: Character to send with Ctrl (e.g., 'C' for Ctrl-C)
        """
        if self.in_debugger:
            self.exit_debugger()
        self.process.sendcontrol(char.lower())

    def get_registers(self) -> dict:
        """Get CPU register values.

        Returns:
            Dict with A, X, Y, SP, PC, and flags
        """
        if not self.in_debugger:
            self.enter_debugger()

        # The debugger shows registers on entry
        # ACC: A0  X: 00  Y: 05  SP: F4          [N]   V   [U]  [B]   D    I    Z    C
        output = self.debugger_command("")

        registers = {
            'A': 0, 'X': 0, 'Y': 0, 'SP': 0, 'PC': 0,
            'N': False, 'V': False, 'B': False,
            'D': False, 'I': False, 'Z': False, 'C': False
        }

        # Parse ACC, X, Y, SP
        acc_match = re.search(r'ACC:\s*([0-9A-Fa-f]{2})', output)
        if acc_match:
            registers['A'] = int(acc_match.group(1), 16)

        x_match = re.search(r'X:\s*([0-9A-Fa-f]{2})', output)
        if x_match:
            registers['X'] = int(x_match.group(1), 16)

        y_match = re.search(r'Y:\s*([0-9A-Fa-f]{2})', output)
        if y_match:
            registers['Y'] = int(y_match.group(1), 16)

        sp_match = re.search(r'SP:\s*([0-9A-Fa-f]{2})', output)
        if sp_match:
            registers['SP'] = int(sp_match.group(1), 16)

        # Parse PC from instruction line (e.g., "0300:   B1 28")
        pc_match = re.search(r'^([0-9A-Fa-f]{4}):', output, re.MULTILINE)
        if pc_match:
            registers['PC'] = int(pc_match.group(1), 16)

        # Parse flags (bracketed = set)
        for flag in ['N', 'V', 'B', 'D', 'I', 'Z', 'C']:
            if f'[{flag}]' in output:
                registers[flag] = True

        return registers

    def reset(self, cold: bool = False) -> None:
        """Reset the emulator.

        Args:
            cold: If True, do a cold reset (full reboot). Otherwise warm reset.
        """
        if not self.in_debugger:
            self.enter_debugger()

        if cold:
            self.debugger_command("rr")
        else:
            self.debugger_command("r")

        self.in_debugger = False

    def save_ram(self, filepath: str) -> bool:
        """Dump all RAM to a file.

        Args:
            filepath: Path to save RAM dump

        Returns:
            True if successful
        """
        self.debugger_command(f"save-ram {filepath}")
        return Path(filepath).exists()

    def wait_for_prompt(self, prompt: str = "]", timeout: float = 10.0) -> str:
        """Wait for a specific prompt character.

        Args:
            prompt: Prompt character to wait for
            timeout: Maximum wait time

        Returns:
            Text before the prompt
        """
        if self.in_debugger:
            self.exit_debugger()

        try:
            self.process.expect(re.escape(prompt), timeout=timeout)
            return self.process.before
        except pexpect.TIMEOUT:
            raise BobbinError(f"Timeout waiting for prompt '{prompt}'")

    def run_basic_command(self, command: str, timeout: float = 30.0) -> str:
        """Type a BASIC command and wait for the prompt to return.

        Args:
            command: BASIC command to execute
            timeout: Maximum wait time

        Returns:
            Output from the command
        """
        self.type_text(command, include_return=True)
        return self.wait_for_prompt("]", timeout=timeout)

    def capture_hgr(self, filepath: str, page: int = 1,
                    format: str = "ppm", color: bool = False) -> bool:
        """Capture HGR graphics to a file.

        Args:
            filepath: Output file path
            page: HGR page (1 or 2)
            format: Output format ('ascii', 'ppm')
            color: Use color mode for PPM (artifact colors)

        Returns:
            True if successful
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            self.enter_debugger()

        # Build command based on format and page
        if format == "ascii":
            cmd = f"sha{'' if page == 1 else '2'} {filepath}"
        elif format == "ppm" and color:
            cmd = f"save-hgr{'' if page == 1 else '2'}-ppm-color {filepath}"
        else:  # ppm mono
            cmd = f"shp{'' if page == 1 else '2'} {filepath}"

        output = self.debugger_command(cmd)

        if not was_in_debugger:
            self.exit_debugger()

        return "Saved" in output

    def capture_gr(self, filepath: str, page: int = 1,
                   format: str = "ppm", native: bool = False) -> bool:
        """Capture GR (lo-res) graphics to a file.

        Args:
            filepath: Output file path
            page: GR page (1 or 2)
            format: Output format ('ascii', 'ppm')
            native: If True, save at native 40x48 resolution (ppm only)

        Returns:
            True if successful
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            self.enter_debugger()

        # Build command based on format and page
        page_suffix = "" if page == 1 else "2"
        if format == "ascii":
            cmd = f"sga{page_suffix} {filepath}"
        elif format == "ppm" and native:
            cmd = f"save-gr{page_suffix}-ppm-native {filepath}"
        else:  # ppm scaled
            cmd = f"sgp{page_suffix} {filepath}"

        output = self.debugger_command(cmd)

        if not was_in_debugger:
            self.exit_debugger()

        return "Saved" in output

    def capture_dhgr(self, filepath: str, page: int = 1,
                     format: str = "ppm") -> bool:
        """Capture DHGR (double hi-res) graphics to a file.

        Requires Apple //e with aux memory (128KB mode).

        Args:
            filepath: Output file path
            page: DHGR page (1 or 2)
            format: Output format ('ascii', 'ppm')

        Returns:
            True if successful
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            self.enter_debugger()

        # Build command based on format and page
        page_suffix = "" if page == 1 else "2"
        if format == "ascii":
            cmd = f"sdha{page_suffix} {filepath}"
        else:  # ppm
            cmd = f"sdhp{page_suffix} {filepath}"

        output = self.debugger_command(cmd)

        if not was_in_debugger:
            self.exit_debugger()

        return "Saved" in output

    def capture_dgr(self, filepath: str, page: int = 1,
                    format: str = "ppm", native: bool = False) -> bool:
        """Capture DGR (double lo-res) graphics to a file.

        Requires Apple //e with aux memory (128KB mode).

        Args:
            filepath: Output file path
            page: DGR page (1 or 2)
            format: Output format ('ascii', 'ppm')
            native: If True, save at native 80x48 resolution (ppm only)

        Returns:
            True if successful
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            self.enter_debugger()

        # Build command based on format and page
        page_suffix = "" if page == 1 else "2"
        if format == "ascii":
            cmd = f"sdga{page_suffix} {filepath}"
        elif format == "ppm" and native:
            cmd = f"save-dgr{page_suffix}-ppm-native {filepath}"
        else:  # ppm scaled
            cmd = f"sdgp{page_suffix} {filepath}"

        output = self.debugger_command(cmd)

        if not was_in_debugger:
            self.exit_debugger()

        return "Saved" in output
