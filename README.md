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

- `boot` - Start the Apple II emulator
- `peek` / `poke` - Read/write memory
- `read_screen` - Get 40x24 text display
- `type_text` - Type into the emulator
- `type_and_capture` - Type BASIC and see tokenization
- `inject_tokenized_basic` - Direct memory injection
- `record_technique` / `query_techniques` - Knowledge base

## Requirements

- Python 3.10+
- Bobbin emulator (compiled)
- pexpect
- mcp
