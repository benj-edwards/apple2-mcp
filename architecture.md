# Apple II MCP Server Architecture

An MCP server for **autonomous experimental learning** of Apple II control techniques. The agent uses an emulated Apple II as a sandbox to discover injection methods, memory manipulation patterns, and execution triggers — building transferable knowledge for a real Apple II system connected via Uthernet.

## The Real System (Context)

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR PRODUCTION SETUP                                          │
│                                                                 │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────────┐  │
│  │ Claude Code │ ───▶ │   Proxy     │ ───▶ │ Real Apple II   │  │
│  │             │      │             │  TCP │ + Uthernet      │  │
│  │ generates   │      │ tokenizes   │      │ + injection     │  │
│  │ BASIC/ASM   │      │ BASIC to    │      │   client        │  │
│  │             │      │ binary      │      │                 │  │
│  │             │      │             │      │ receives &      │  │
│  │             │      │ sends via   │      │ injects into    │  │
│  │             │      │ network     │      │ memory          │  │
│  └─────────────┘      └─────────────┘      └─────────────────┘  │
│                                                                 │
│  PROBLEM: What are the BEST techniques for injection?           │
│           What memory addresses? What pointers to update?       │
│           What triggers execution? What are the edge cases?     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## This MCP Server (Training Ground)

```
┌─────────────────────────────────────────────────────────────────┐
│  EXPERIMENTAL LEARNING ENVIRONMENT                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Claude Agent (autonomous, runs for hours)              │    │
│  │                                                         │    │
│  │  LOOP:                                                  │    │
│  │   1. Form hypothesis: "If I poke X at $YYYY, then..."   │    │
│  │   2. Execute experiment via MCP tools                   │    │
│  │   3. Observe result (screen, memory, crash, success)    │    │
│  │   4. Record finding in knowledge base                   │    │
│  │   5. Refine technique or try new approach               │    │
│  │   6. GOTO 1                                             │    │
│  │                                                         │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │ MCP Protocol                        │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │  apple2-mcp-server                                      │    │
│  │                                                         │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │ Emulator Control    │ Experimentation           │    │    │
│  │  │  • boot / reset     │  • run_experiment         │    │    │
│  │  │  • shutdown         │  • compare_states         │    │    │
│  │  │  • snapshot/restore │  • detect_crash           │    │    │
│  │  ├─────────────────────┼───────────────────────────┤    │    │
│  │  │ Raw Memory Access   │ Knowledge Base            │    │    │
│  │  │  • peek (1-64K)     │  • record_technique       │    │    │
│  │  │  • poke (1-64K)     │  • query_techniques       │    │    │
│  │  │  • dump_region      │  • mark_success/failure   │    │    │
│  │  │  • load_binary      │  • get_known_addresses    │    │    │
│  │  ├─────────────────────┼───────────────────────────┤    │    │
│  │  │ Observation         │ Injection Helpers         │    │    │
│  │  │  • read_screen      │  • inject_tokenized_basic │    │    │
│  │  │  • get_registers    │  • inject_binary          │    │    │
│  │  │  • get_soft_switches│  • update_pointers        │    │    │
│  │  │  • trace_execution  │  • trigger_run            │    │    │
│  │  └─────────────────────┴───────────────────────────┘    │    │
│  │                                                         │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │ PTY + Debugger                      │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │  Bobbin Emulator (full 64K access, debugger, snapshots) │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  KNOWLEDGE BASE (persisted, transferable)               │    │
│  │                                                         │    │
│  │  techniques.json:                                       │    │
│  │  {                                                      │    │
│  │    "inject_tokenized_basic": {                          │    │
│  │      "method": "poke to $0801+, update TXTTAB/VARTAB",  │    │
│  │      "pointers": {                                      │    │
│  │        "TXTTAB": "$67-68 (start of program)",           │    │
│  │        "VARTAB": "$69-6A (end of program + 1)",         │    │
│  │        "ARYTAB": "$6B-6C",                              │    │
│  │        "STREND": "$6D-6E"                               │    │
│  │      },                                                 │    │
│  │      "trigger": "JSR $D566 (RUN) or type RUN",          │    │
│  │      "tested": true,                                    │    │
│  │      "success_rate": 0.98,                              │    │
│  │      "edge_cases": ["long programs need HIMEM check"]   │    │
│  │    },                                                   │    │
│  │    ...                                                  │    │
│  │  }                                                      │    │
│  │                                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  TRANSFER TO REAL SYSTEM                                │    │
│  │                                                         │    │
│  │  Agent says: "Here's what I learned works:"             │    │
│  │   • Tokenized BASIC injection: poke at $0801, set       │    │
│  │     TXTTAB=$0801, VARTAB=end+1, call $D566              │    │
│  │   • Binary injection: load at $6000, JSR $6000          │    │
│  │   • Screen control: POKE $22 for VTAB, $24 for HTAB     │    │
│  │   • Safe to call: $FDED (COUT), $FD0C (RDKEY)           │    │
│  │   • Edge case: always clear $C000 before keyboard read  │    │
│  │                                                         │    │
│  │  Your proxy can now use these techniques with the       │    │
│  │  real Apple II via Uthernet                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Design Principles

### 1. Unrestricted Memory Access
The agent needs raw access to all 64K of memory. No abstraction layers that hide complexity.

### 2. Experiment-Observe-Learn Loop
Every tool call should enable the agent to:
- Try something
- See what happened
- Record the result

### 3. Transferable Knowledge
Techniques learned in the emulator must work on real hardware. Focus on:
- Memory addresses and their purposes
- ROM entry points
- Pointer manipulation
- Timing considerations (where applicable)

### 4. Long-Running Autonomy
The agent should be able to run for 10+ hours without intervention, systematically exploring the Apple II's behavior.

### 5. Crash Recovery
When experiments crash the emulator, automatic recovery via snapshot restore.

## Tool Specifications

### Emulator Control

#### boot
```json
{
  "name": "boot",
  "description": "Start Apple II emulator. Returns when at BASIC prompt.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "machine": {
        "type": "string",
        "enum": ["plus", "enhanced"],
        "default": "enhanced",
        "description": "Machine type (plus=II+, enhanced=//e)"
      },
      "snapshot": {
        "type": "string",
        "description": "Optional: restore from named snapshot instead of cold boot"
      }
    }
  }
}
```

#### reset
```json
{
  "name": "reset",
  "description": "Reset the emulator (warm or cold)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "cold": {
        "type": "boolean",
        "default": false,
        "description": "Cold reset (full reboot) vs warm reset (CTRL-RESET)"
      }
    }
  }
}
```

#### snapshot
```json
{
  "name": "snapshot",
  "description": "Save or restore complete machine state",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["save", "restore", "list"],
        "description": "Save current state, restore previous, or list available"
      },
      "name": {
        "type": "string",
        "description": "Snapshot name (auto-generated if not provided for save)"
      }
    },
    "required": ["action"]
  }
}
```

### Raw Memory Access

#### peek
```json
{
  "name": "peek",
  "description": "Read bytes from Apple II memory",
  "inputSchema": {
    "type": "object",
    "properties": {
      "address": {
        "type": "integer",
        "minimum": 0,
        "maximum": 65535,
        "description": "Starting address (0-65535 or $0000-$FFFF)"
      },
      "count": {
        "type": "integer",
        "default": 1,
        "minimum": 1,
        "maximum": 65536,
        "description": "Number of bytes to read"
      },
      "format": {
        "type": "string",
        "enum": ["hex", "decimal", "ascii", "disasm"],
        "default": "hex",
        "description": "Output format"
      }
    },
    "required": ["address"]
  }
}
```

#### poke
```json
{
  "name": "poke",
  "description": "Write bytes to Apple II memory",
  "inputSchema": {
    "type": "object",
    "properties": {
      "address": {
        "type": "integer",
        "minimum": 0,
        "maximum": 65535,
        "description": "Starting address"
      },
      "data": {
        "oneOf": [
          {"type": "integer", "minimum": 0, "maximum": 255},
          {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 255}},
          {"type": "string", "description": "Hex string like 'A9 00 8D 00 C0'"}
        ],
        "description": "Byte(s) to write"
      }
    },
    "required": ["address", "data"]
  }
}
```

#### load_binary
```json
{
  "name": "load_binary",
  "description": "Load binary data into memory from base64 or hex",
  "inputSchema": {
    "type": "object",
    "properties": {
      "address": {
        "type": "integer",
        "description": "Load address"
      },
      "data": {
        "type": "string",
        "description": "Binary data as base64 or hex string"
      },
      "encoding": {
        "type": "string",
        "enum": ["base64", "hex"],
        "default": "hex"
      }
    },
    "required": ["address", "data"]
  }
}
```

### Observation

#### read_screen
```json
{
  "name": "read_screen",
  "description": "Read current 40x24 text screen contents",
  "inputSchema": {
    "type": "object",
    "properties": {
      "include_cursor": {
        "type": "boolean",
        "default": true,
        "description": "Show cursor position marker"
      }
    }
  }
}
```

Returns plain text representation of the screen.

#### get_registers
```json
{
  "name": "get_registers",
  "description": "Get current 6502 CPU register state",
  "inputSchema": {"type": "object", "properties": {}}
}
```

Returns:
```json
{
  "A": 0,
  "X": 0,
  "Y": 0,
  "SP": 255,
  "PC": 65024,
  "P": {
    "N": false, "V": false, "B": false,
    "D": false, "I": true, "Z": true, "C": false
  }
}
```

#### compare_memory
```json
{
  "name": "compare_memory",
  "description": "Compare current memory region to a previous snapshot or expected values",
  "inputSchema": {
    "type": "object",
    "properties": {
      "address": {"type": "integer"},
      "count": {"type": "integer"},
      "expected": {
        "type": "string",
        "description": "Expected hex values, or 'snapshot:name' to compare to snapshot"
      }
    },
    "required": ["address", "count", "expected"]
  }
}
```

### Experimentation

#### run_experiment
```json
{
  "name": "run_experiment",
  "description": "Execute a hypothesis test with automatic state capture",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Experiment name for logging"
      },
      "hypothesis": {
        "type": "string",
        "description": "What you expect to happen"
      },
      "setup": {
        "type": "array",
        "items": {
          "type": "object",
          "description": "Tool calls to set up the experiment"
        },
        "description": "Setup steps (pokes, loads, etc)"
      },
      "trigger": {
        "type": "object",
        "description": "The action that triggers the test (type_text, call address, etc)"
      },
      "observe": {
        "type": "array",
        "items": {"type": "string"},
        "description": "What to observe: 'screen', 'memory:$ADDR:COUNT', 'registers'"
      },
      "success_criteria": {
        "type": "string",
        "description": "How to determine if experiment succeeded"
      }
    },
    "required": ["name", "hypothesis", "trigger", "observe"]
  }
}
```

Returns:
```json
{
  "experiment": "inject_basic_at_0801",
  "hypothesis": "Tokenized BASIC at $0801 with updated TXTTAB will RUN",
  "result": "success",
  "observations": {
    "screen": "]RUN\nHELLO WORLD\n]",
    "memory:$67:4": "01 08 15 08",
    "registers": {"A": 0, "PC": 65024}
  },
  "duration_ms": 1250,
  "crash": false
}
```

### Knowledge Base

#### record_technique
```json
{
  "name": "record_technique",
  "description": "Save a discovered technique to the knowledge base",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Technique name (e.g., 'inject_tokenized_basic')"
      },
      "category": {
        "type": "string",
        "enum": ["injection", "execution", "screen", "keyboard", "disk", "memory", "other"]
      },
      "description": {
        "type": "string",
        "description": "What this technique does"
      },
      "steps": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Step-by-step instructions"
      },
      "memory_addresses": {
        "type": "object",
        "description": "Key addresses involved: {'TXTTAB': '$67-68', ...}"
      },
      "code_example": {
        "type": "string",
        "description": "Example implementation"
      },
      "success_rate": {
        "type": "number",
        "minimum": 0,
        "maximum": 1
      },
      "edge_cases": {
        "type": "array",
        "items": {"type": "string"}
      },
      "transferable": {
        "type": "boolean",
        "default": true,
        "description": "Will this work on real hardware?"
      }
    },
    "required": ["name", "category", "description", "steps"]
  }
}
```

#### query_techniques
```json
{
  "name": "query_techniques",
  "description": "Search the knowledge base for techniques",
  "inputSchema": {
    "type": "object",
    "properties": {
      "category": {"type": "string"},
      "search": {"type": "string", "description": "Full-text search"},
      "min_success_rate": {"type": "number"}
    }
  }
}
```

#### get_known_addresses
```json
{
  "name": "get_known_addresses",
  "description": "Get all documented memory addresses and their purposes",
  "inputSchema": {
    "type": "object",
    "properties": {
      "region": {
        "type": "string",
        "enum": ["zeropage", "stack", "text", "hires", "io", "rom", "all"],
        "default": "all"
      }
    }
  }
}
```

### Tokenization Discovery

#### type_and_capture
```json
{
  "name": "type_and_capture",
  "description": "Type a BASIC line and capture how Apple II tokenizes it",
  "inputSchema": {
    "type": "object",
    "properties": {
      "basic_line": {
        "type": "string",
        "description": "BASIC line to type (e.g., '10 FOR I=1 TO 10')"
      },
      "capture_range": {
        "type": "integer",
        "default": 256,
        "description": "Bytes to capture from $0801"
      }
    },
    "required": ["basic_line"]
  }
}
```

Returns:
```json
{
  "typed": "10 FOR I=1 TO 10",
  "tokenized_hex": "0D 08 0A 00 81 49 D0 31 C4 31 30 00 00 00",
  "tokenized_annotated": [
    {"offset": 0, "bytes": "0D 08", "meaning": "next line ptr"},
    {"offset": 2, "bytes": "0A 00", "meaning": "line number 10"},
    {"offset": 4, "bytes": "81", "meaning": "FOR token"},
    {"offset": 5, "bytes": "49", "meaning": "'I' (variable)"},
    {"offset": 6, "bytes": "D0", "meaning": "'=' token"},
    {"offset": 7, "bytes": "31", "meaning": "'1' ASCII"},
    {"offset": 8, "bytes": "C4", "meaning": "TO token"},
    {"offset": 9, "bytes": "31 30", "meaning": "'10' ASCII"},
    {"offset": 11, "bytes": "00", "meaning": "end of line"},
    {"offset": 12, "bytes": "00 00", "meaning": "end of program"}
  ],
  "length": 14
}
```

#### compare_tokenization
```json
{
  "name": "compare_tokenization",
  "description": "Compare your tokenization against Apple II native tokenization",
  "inputSchema": {
    "type": "object",
    "properties": {
      "basic_line": {
        "type": "string",
        "description": "BASIC source line"
      },
      "your_tokenization": {
        "type": "string",
        "description": "Your tokenized output as hex string"
      }
    },
    "required": ["basic_line", "your_tokenization"]
  }
}
```

Returns:
```json
{
  "basic_line": "10 FOR I=1 TO 10",
  "apple_tokenized": "0D 08 0A 00 81 49 D0 31 C4 31 30 00",
  "your_tokenized":  "0D 08 0A 00 81 49 D0 31 54 4F 31 30 00",
  "match": false,
  "differences": [
    {
      "offset": 8,
      "apple": "C4 (TO token)",
      "yours": "54 4F ('TO' ASCII)",
      "issue": "TO should be tokenized as $C4 in FOR..TO context"
    }
  ],
  "verdict": "MISMATCH: TO keyword not tokenized"
}
```

#### discover_tokenization_rules
```json
{
  "name": "discover_tokenization_rules",
  "description": "Run systematic tests to discover tokenization edge cases",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {
        "type": "string",
        "description": "Keyword to test (e.g., 'TO', 'OR', 'AND')"
      },
      "contexts": {
        "type": "array",
        "items": {"type": "string"},
        "description": "BASIC line templates with {KW} placeholder",
        "default": [
          "10 FOR I=1 {KW} 10",
          "10 A{KW}B=1",
          "10 X={KW}TAL",
          "10 PRINT \"{KW}\"",
          "10 REM {KW}",
          "10 IF A {KW} B"
        ]
      }
    },
    "required": ["keyword"]
  }
}
```

Returns:
```json
{
  "keyword": "TO",
  "token_value": "0xC4",
  "results": [
    {"context": "FOR I=1 TO 10", "tokenized_as": "token", "hex": "C4"},
    {"context": "ATOB=1", "tokenized_as": "ascii", "hex": "54 4F"},
    {"context": "X=TOTAL", "tokenized_as": "ascii", "hex": "54 4F"},
    {"context": "PRINT \"TO\"", "tokenized_as": "ascii (in string)", "hex": "54 4F"},
    {"context": "REM TO", "tokenized_as": "ascii (in REM)", "hex": "54 4F"},
    {"context": "IF A TO B", "tokenized_as": "token", "hex": "C4"}
  ],
  "rule_hypothesis": "TO tokenizes as $C4 only when: (1) preceded by space or operator, (2) followed by space or number, (3) not inside string/REM, (4) not part of variable name"
}
```

### Injection Helpers

#### inject_tokenized_basic
```json
{
  "name": "inject_tokenized_basic",
  "description": "Inject pre-tokenized BASIC program into memory and update pointers",
  "inputSchema": {
    "type": "object",
    "properties": {
      "tokenized_data": {
        "type": "string",
        "description": "Tokenized BASIC as hex string (same format your proxy uses)"
      },
      "load_address": {
        "type": "integer",
        "default": 2049,
        "description": "Where to load ($0801 default)"
      },
      "update_pointers": {
        "type": "boolean",
        "default": true,
        "description": "Automatically update TXTTAB, VARTAB, etc."
      },
      "auto_run": {
        "type": "boolean",
        "default": false,
        "description": "Trigger RUN after injection"
      }
    },
    "required": ["tokenized_data"]
  }
}
```

#### trigger_execution
```json
{
  "name": "trigger_execution",
  "description": "Trigger code execution via various methods",
  "inputSchema": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "enum": ["run_command", "call_address", "jsr", "jmp", "usr"],
        "description": "How to trigger execution"
      },
      "address": {
        "type": "integer",
        "description": "Address for call/jsr/jmp methods"
      }
    },
    "required": ["method"]
  }
}
```

### Input

#### type_text
```json
{
  "name": "type_text",
  "description": "Type text into Apple II keyboard buffer",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "description": "Text to type (auto-uppercased)"
      },
      "include_return": {
        "type": "boolean",
        "default": true,
        "description": "Press RETURN after text"
      }
    },
    "required": ["text"]
  }
}
```

#### send_key
```json
{
  "name": "send_key",
  "description": "Send special key",
  "inputSchema": {
    "type": "object",
    "properties": {
      "key": {
        "type": "string",
        "enum": ["RETURN", "ESCAPE", "CTRL-C", "CTRL-RESET", "LEFT", "RIGHT", "UP", "DOWN", "DELETE"],
        "description": "Special key to send"
      }
    },
    "required": ["key"]
  }
}
```

## Apple II Memory Map Reference

Embedded in the server for agent reference:

```
$0000-$00FF  Zero Page (critical system variables)
  $20       Text window left edge
  $21       Text window width
  $22       Text window top (VTAB)
  $23       Text window bottom
  $24       Cursor horizontal (HTAB)
  $25       Cursor vertical
  $67-$68   TXTTAB - Start of BASIC program
  $69-$6A   VARTAB - Start of BASIC variables (end of program)
  $6B-$6C   ARYTAB - Start of arrays
  $6D-$6E   STREND - End of string storage
  $6F-$70   FRETOP - Top of string free space
  $73-$74   HIMEM  - Highest address available to BASIC
  $AF-$B0   PRGEND - End of program

$0100-$01FF  Stack

$0200-$02FF  Input buffer (keyboard)
  $0200-$027F  Line input buffer

$0300-$03FF  System vectors, DOS hooks

$0400-$07FF  Text Page 1 (40x24 display)
$0800       Usually empty (reserved)
$0801-$BFFF  BASIC program area (default start $0801)

$C000-$C0FF  Soft switches (I/O)
  $C000    Keyboard data (read)
  $C010    Clear keyboard strobe
  $C050    Graphics mode
  $C051    Text mode
  $C052    Full screen
  $C053    Mixed mode
  $C054    Page 1
  $C055    Page 2
  $C056    Lo-res
  $C057    Hi-res

$D000-$FFFF  ROM (BASIC interpreter, Monitor)
  $D566    RUN entry point
  $E000    Applesoft cold start
  $F800    Monitor entry
  $FB60    INIT - Initialize text screen
  $FC58    HOME - Clear screen
  $FCA8    WAIT - Delay routine
  $FD0C    RDKEY - Read keyboard
  $FDED    COUT - Output character
  $FDF0    COUT1 - Output character (no scroll)
```

## Knowledge Base Schema

`knowledge/techniques.json`:
```json
{
  "version": 1,
  "techniques": [
    {
      "id": "inject_tokenized_basic_0801",
      "name": "Inject Tokenized BASIC at $0801",
      "category": "injection",
      "description": "Load pre-tokenized Applesoft BASIC into standard program area",
      "steps": [
        "Write tokenized bytes starting at $0801",
        "Set TXTTAB ($67-68) to $0801 (little-endian: 01 08)",
        "Set VARTAB ($69-6A) to program_end + 1",
        "Set ARYTAB ($6B-6C) to same as VARTAB",
        "Set STREND ($6D-6E) to same as VARTAB",
        "Call RUN via JSR $D566 or type 'RUN' command"
      ],
      "memory_addresses": {
        "TXTTAB": {"address": "0x67", "size": 2, "purpose": "Start of program"},
        "VARTAB": {"address": "0x69", "size": 2, "purpose": "End of program"},
        "ARYTAB": {"address": "0x6B", "size": 2, "purpose": "Array storage start"},
        "STREND": {"address": "0x6D", "size": 2, "purpose": "String storage end"}
      },
      "tested_count": 47,
      "success_count": 46,
      "success_rate": 0.979,
      "edge_cases": [
        "Programs over 38K need HIMEM check",
        "Must end with 00 00 00 (triple null terminator)",
        "Line numbers must be ascending"
      ],
      "transferable": true,
      "created": "2025-01-03T10:00:00Z",
      "experiments": ["exp_001", "exp_002", "exp_015"]
    }
  ],
  "experiments": [
    {
      "id": "exp_001",
      "timestamp": "2025-01-03T10:05:00Z",
      "name": "basic_injection_test_1",
      "hypothesis": "Tokenized 10 PRINT HELLO at $0801 will RUN",
      "result": "success",
      "duration_ms": 850,
      "notes": "Clean execution, screen showed output correctly"
    }
  ],
  "discovered_addresses": {
    "0x67": {"name": "TXTTAB_LO", "purpose": "Program start low byte", "confidence": 1.0},
    "0x68": {"name": "TXTTAB_HI", "purpose": "Program start high byte", "confidence": 1.0}
  }
}
```

## Autonomous Agent Loop

The agent should follow this pattern:

```
PHASE 1: EXPLORATION (hours 0-2)
  - Dump and analyze key memory regions
  - Identify what changes when user types/runs programs manually
  - Map out unknown zero-page locations
  - Test ROM entry points

PHASE 2: TOKENIZATION MAPPING (hours 2-5)
  - Test EVERY Applesoft keyword in multiple contexts
  - Discover context-dependent tokenization rules
  - Build complete tokenization rule set
  - Edge cases to test:
    • Keywords inside variable names (ATOB, FORA, NEXTA)
    • Keywords inside strings ("PRINT", "FOR")
    • Keywords after REM
    • Keywords with/without surrounding spaces
    • Chained keywords (THENPRINT, ELSEFOR)
    • Numeric contexts (TO10 vs TO 10)
    • Special cases: DATA statements, colon separators

PHASE 3: INJECTION TESTING (hours 5-7)
  - Test injection with perfectly-matched tokenization
  - Test pointer update sequences
  - Test execution triggers
  - Test re-injection (overwrite existing program)
  - Test large programs (near HIMEM)
  - Test programs with variables already present

PHASE 4: EDGE CASE HUNTING (hours 7-9)
  - Malformed line numbers
  - Maximum line length
  - Unusual characters
  - Empty lines
  - Lines with only REM
  - Programs that modify themselves
  - Programs that POKE into program area

PHASE 5: SYNTHESIS (hours 9-10)
  - Compile IRONCLAD tokenization rules
  - Generate transfer document for real hardware
  - Create test suite for proxy validation
  - Document all discovered edge cases
```

## Tokenization Problem Space

The core challenge: Applesoft's tokenizer has **context-dependent** behavior.

### Known Problematic Keywords

These short keywords appear inside other words and need careful handling:

| Keyword | Token | Problem |
|---------|-------|---------|
| TO      | $C4   | TOTAL, ATOB, VECTOR |
| OR      | $AF   | FOR, WORD, COLOR |
| AN      | $A7   | RANDOM, PLAN |
| AT      | $C5   | DATA, FATAL |
| IF      | $E7   | ELIF, LIFE |
| ON      | $C6   | DONE, FONT |
| GO      | $AB   | LOGO, ERGO |
| LET     | $AA   | DELETE, LETTER |
| NOT     | $C8   | NOTE, KNOT |
| AND     | $AD   | GRAND, WAND |
| FN      | $C2   | Often part of function names |

### Tokenization Rules to Discover

The agent must determine through experimentation:

1. **Word boundary detection** - What constitutes a "boundary"?
   - Space before/after?
   - Operators? (=, +, -, etc.)
   - Parentheses?
   - Colon (statement separator)?

2. **State-dependent parsing** - Does tokenizer have modes?
   - After REM: all ASCII until EOL
   - Inside quotes: all ASCII until close quote
   - Inside DATA: partially tokenized?

3. **Keyword priority** - When keywords overlap, which wins?
   - GOTO vs GO + TO
   - ONERR vs ON + ERR
   - THENPRINT vs THEN + PRINT

4. **Case sensitivity** - Apple II is uppercase only but:
   - Are lowercase chars in input converted first?
   - Or passed through as ASCII?

### Target Output

After tokenization mapping, the agent produces:

```json
{
  "tokenization_rules": {
    "TO": {
      "token": "0xC4",
      "tokenize_when": [
        "preceded by space/operator AND followed by space/digit",
        "after FOR...= (FOR loop context)"
      ],
      "keep_ascii_when": [
        "part of variable name (A-Z before or after)",
        "inside string literal",
        "after REM"
      ],
      "test_coverage": 47,
      "confidence": 0.99
    }
  }
}
```

## File Structure

```
apple2-mcp/
├── pyproject.toml
├── architecture.md
├── src/
│   └── apple2_mcp/
│       ├── __init__.py
│       ├── server.py              # MCP server entry point
│       ├── emulator.py            # Bobbin process manager
│       ├── memory.py              # Memory access helpers
│       ├── screen.py              # Screen decoding
│       ├── knowledge.py           # Knowledge base management
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── machine.py         # boot, reset, snapshot
│       │   ├── memory.py          # peek, poke, load_binary
│       │   ├── observe.py         # read_screen, get_registers
│       │   ├── experiment.py      # run_experiment, compare_memory
│       │   ├── knowledge.py       # record_technique, query
│       │   ├── injection.py       # inject_tokenized_basic, trigger
│       │   └── input.py           # type_text, send_key
│       ├── encoding.py            # Apple II character encoding
│       └── apple2_memmap.py       # Memory map constants
├── knowledge/
│   ├── techniques.json            # Learned techniques (persisted)
│   ├── experiments.json           # Experiment history
│   └── addresses.json             # Discovered addresses
├── snapshots/                     # Machine state snapshots
└── tests/
    └── ...
```

## Transfer Document Output

After running, the agent produces `knowledge/transfer.md`:

```markdown
# Apple II Control Techniques (Transfer Document)

These techniques were validated in emulation and should work on real hardware.

## Tokenized BASIC Injection

### Method
1. Send tokenized bytes to Apple II starting at $0801
2. Update zero-page pointers via POKE or direct memory write:
   - $67-68 = $0801 (program start)
   - $69-6A = end_address + 1 (variables start)
   - $6B-6C = same as $69-6A
   - $6D-6E = same as $69-6A
3. Trigger execution via:
   - Type "RUN" + RETURN, or
   - JSR $D566 (direct entry), or
   - CALL 54630

### Tokenized Format
[Detailed format documentation...]

### Your Proxy Should
1. Tokenize BASIC source (you have this)
2. Send: {load_address, length, tokenized_bytes}
3. Client pokes bytes and updates pointers
4. Client triggers RUN

### Edge Cases
- Maximum program size: ~38K (check HIMEM at $73-74)
- Ensure triple-null terminator (00 00 00) at end
- Clear variables first if re-injecting (set VARTAB = TXTTAB + 1)
```

## Dependencies

- Python 3.10+
- `mcp` - Official MCP Python SDK
- `pexpect` - PTY handling
- Bobbin emulator (compiled)

## Success Criteria

The MCP server is successful when an agent can:

1. Boot the emulator and reach BASIC prompt
2. Inject tokenized BASIC identical to what your proxy sends
3. Trigger execution and observe results
4. Discover and document the exact pointer update sequence
5. Handle edge cases (long programs, re-injection, errors)
6. Produce a transfer document your proxy can use

The agent becomes an Apple II expert through experimentation, not training data.
