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
             timeout: float = 10.0) -> str:
        """Start the emulator and wait for BASIC prompt.

        Args:
            machine: Machine type (plus, enhanced, twoey, original)
            disk: Optional disk image path to load

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
            return True

        # Send Ctrl-C twice
        self.process.sendcontrol('c')
        time.sleep(0.1)
        self.process.sendcontrol('c')

        # Wait for debugger prompt
        try:
            self.process.expect(r'>', timeout=timeout)
            self.in_debugger = True
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

        self.process.sendline("c")
        self.in_debugger = False
        return True

    def debugger_command(self, cmd: str, timeout: float = 2.0) -> str:
        """Execute a debugger command and return output.

        Args:
            cmd: Command to execute

        Returns:
            Command output
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        was_in_debugger = self.in_debugger
        if not was_in_debugger:
            self.enter_debugger()

        self.process.sendline(cmd)

        # Wait for next prompt
        try:
            self.process.expect(r'\n>', timeout=timeout)
            output = self.process.before
        except pexpect.TIMEOUT:
            output = self.process.before if self.process.before else ""

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
            output = self.debugger_command(f"{address:04X}")
        else:
            # Range
            end_addr = min(address + count - 1, 0xFFFF)
            output = self.debugger_command(f"{address:04X}.{end_addr:04X}")

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

        # Build command: "addr: val val val..."
        hex_values = ' '.join(f"{b:02X}" for b in data)
        cmd = f"{address:04X}: {hex_values}"

        self.debugger_command(cmd)
        return True

    def read_screen_memory(self) -> dict[int, int]:
        """Read the entire text screen memory.

        Returns:
            Dict mapping addresses to byte values
        """
        memory = {}

        # Read text page 1 ($0400-$07FF)
        data = self.peek(0x0400, 0x0400)

        for i, byte in enumerate(data):
            memory[0x0400 + i] = byte

        return memory

    def read_screen(self) -> list[str]:
        """Read the current screen contents as text.

        Returns:
            List of 24 strings, each 40 characters
        """
        memory = self.read_screen_memory()
        return decode_screen(memory)

    def type_text(self, text: str, delay: float = 0.02,
                  include_return: bool = False) -> None:
        """Type text into the emulator.

        Args:
            text: Text to type (will be uppercased)
            delay: Delay between keystrokes
            include_return: Add RETURN at end
        """
        if not self.is_running:
            raise BobbinError("Emulator not running")

        # Make sure we're not in debugger
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
