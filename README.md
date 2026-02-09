# Apple II MCP Server

An MCP server for autonomous experimentation with Apple II control techniques via the Bobbin emulator.

## Overview

This MCP server wraps the Bobbin Apple II emulator, providing tools for:
- Memory read/write access
- Screen reading
- BASIC program tokenization and injection
- Knowledge base for recording discovered techniques

## Installation

```bash
pip install -e .
```

## Usage

Configure in your Claude MCP settings:

```json
{
  "mcpServers": {
    "apple2": {
      "command": "apple2-mcp"
    }
  }
}
```

## Tools

### Machine Control
- `boot` - Start the Apple II emulator (Apple II+ or //e)
- `shutdown` - Stop the emulator
- `reset` - Warm or cold reset

### Memory Access
- `peek` / `poke` - Read/write memory
- `load_binary` - Load binary data from hex string

### Screen & Graphics
- `read_screen` - Get 40x24 text display
- `capture_gr` / `read_gr_ascii` - Lo-res graphics (40x48, 16 colors)
- `capture_hgr` / `read_hgr_ascii` - Hi-res graphics (280x192)
- `capture_dgr` / `read_dgr_ascii` - Double lo-res (80x48, //e only)
- `capture_dhgr` / `read_dhgr_ascii` - Double hi-res (560x192, //e only)
- `clear_gr` - Clear lo-res screen to solid color
- `clear_hgr` - Clear hi-res screen to black

### Input
- `type_text` - Type into the emulator
- `send_key` - Send special keys (RETURN, ESCAPE, CTRL-C, CTRL-RESET)

### BASIC Execution
- `run_basic` - Execute BASIC command and wait for prompt
- `run_and_capture` - Run program and capture screen automatically
- `send_keys_and_capture` - Send keys to interactive program, then capture

### Tokenization
- `type_and_capture` - Type BASIC and see tokenization
- `tokenize` - Tokenize BASIC source using Bobbin
- `compare_tokenization` - Compare against native Apple II tokenization
- `inject_tokenized_basic` - Direct memory injection

### Disk Image Tools
- `create_disk` - Create new DOS 3.3 disk image
- `disk_catalog` - List files on disk image
- `save_basic_to_disk` - Save BASIC source to disk (auto-tokenizes)
- `save_file_to_disk` - Save .bas file to disk

### Observation
- `get_registers` - Get 6502 CPU register state
- `get_basic_pointers` - Get BASIC memory pointers

### Knowledge Base
- `record_technique` / `query_techniques` - Save and search techniques

## Requirements

- Python 3.10+
- Bobbin emulator (compiled)
- pexpect
- mcp
