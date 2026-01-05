# AI Development Tips for Apple II MCP

## Token Efficiency - THE MOST IMPORTANT LESSON

One session burned 45K tokens just to draw a checkerboard. That's unacceptable.

**The inefficient approach (DON'T DO THIS):**
- Enter code line-by-line via type_text
- Capture screenshot after every single line
- Restart emulator constantly
- Debug timing issues manually
- 200+ tool calls for one simple program

**The efficient approach (DO THIS):**
1. Write complete BASIC code in a .bas file (think it through first!)
2. `save_basic_to_disk` to save it to a disk image
3. Boot disk and run
4. Capture once to verify

That's 4 tool calls, not 200+.

**When to use detailed step-by-step debugging:**
- ONLY when the efficient approach fails
- ONLY for specific bugs you can't figure out otherwise
- NOT as the default workflow

**Trust the tools:** The `save_basic_to_disk` and `save_file_to_disk` tools work. The tokenizer works. Don't go into paranoid manual mode unless you have a specific reason.

---

## The Catastrophic Failure of January 2026

An AI agent spent hours writing a complex HGR (hi-res graphics) game with 24 animated checker pieces, physics simulation, and page-flipping double buffering. The result:

- First version: "Crosses on an orange background" instead of a checkerboard with round pieces
- Second version: Crashed the emulator entirely

**Root cause:** The AI never once looked at what it was actually rendering. It wrote hundreds of lines of drawing code completely blind, based only on its understanding of how HGR *should* work.

**The irony:** The MCP server has `capture_hgr` which returns a PNG the AI can view. It was never used.

---

## The Golden Rule: Test Small, Verify Visually, Iterate

### Step 1: Boot the Emulator
```
mcp__apple2-mcp__boot(machine="enhanced")
```

### Step 2: Write ONE Small Thing
Don't write a whole program. Write literally one command:
```
mcp__apple2-mcp__run_basic(command="HGR")
```

### Step 3: Capture and LOOK at the Output
```
mcp__apple2-mcp__capture_hgr(format="png")
```
Then use the Read tool on the returned PNG path to actually see what rendered.

### Step 4: Add ONE More Thing
```
mcp__apple2-mcp__run_basic(command="HCOLOR=3:HPLOT 100,100 TO 200,100")
```

### Step 5: Capture Again and Verify
Did a purple line appear? Is it where you expected? Only proceed if yes.

### Step 6: Repeat Until Done
Build up complexity ONE PIECE AT A TIME, verifying each step.

---

## Specific Workflow for Graphics Programs

### For Lo-Res (GR) Graphics:
```
1. run_basic("GR")
2. capture_gr(format="png") -> Read the PNG
3. run_basic("COLOR=4:PLOT 20,20")
4. capture_gr(format="png") -> Verify the pixel appeared
5. Continue...
```

### For Hi-Res (HGR) Graphics:
```
1. run_basic("HGR")
2. capture_hgr(format="png") -> Read the PNG
3. run_basic("HCOLOR=3:HPLOT 140,96")
4. capture_hgr(format="png") -> Verify the pixel appeared
5. run_basic("HPLOT 140,96 TO 200,96")
6. capture_hgr(format="png") -> Verify the line appeared
7. Continue...
```

### For Interactive Programs:
Use `send_keys_and_capture` to send input and see the result:
```
mcp__apple2-mcp__send_keys_and_capture(keys="J", capture_mode="hgr")
```

---

## Common Mistakes to Avoid

### 1. Writing Whole Programs Without Testing
**BAD:** Write 100 lines of BASIC, save to disk, run in external emulator, wonder why it doesn't work.

**GOOD:** Write 3 lines, run in Bobbin, capture output, verify, add 3 more lines.

### 2. Variable Name Collisions
Applesoft BASIC has quirks. If you `DIM Y(23)` and then later do `FOR Y=0 TO 191`, you're reusing Y as both an array and a loop variable. This can crash or corrupt data.

### 3. Assuming Drawing Code Works
HGR has weird color fringing, byte boundaries, and addressing. A "filled circle" routine you write from theory may produce garbage. ALWAYS VERIFY VISUALLY.

### 4. Not Using the Tools Available
The MCP server provides:
- `capture_hgr` / `capture_gr` - Get PNG screenshots
- `read_hgr_ascii` / `read_gr_ascii` - Get ASCII art representation
- `read_screen` - Get text screen contents
- `run_and_capture` - Run a program and capture output

USE THEM.

---

## Checklist Before Declaring "Done"

- [ ] Did you capture a screenshot of the final output?
- [ ] Did you actually LOOK at the screenshot?
- [ ] Does the screenshot show what you intended?
- [ ] Did you test user input (if applicable)?
- [ ] Did you verify the program runs without crashing?
- [ ] Did you test it from a cold boot (not just from current state)?

---

## The Right Way to Build a Complex Program

Example: Building a checkers game with animated pieces

### Phase 1: Static Display
1. Get HGR mode working (capture, verify black screen)
2. Draw one horizontal line (capture, verify)
3. Draw a grid of lines (capture, verify)
4. Fill one square (capture, verify)
5. Fill alternating squares for checkerboard (capture, verify)
6. Draw one circle/piece (capture, verify)
7. Draw all 24 pieces in starting positions (capture, verify)

### Phase 2: User Input
8. Add keyboard reading, print key codes to verify
9. Add cursor movement, capture after each keypress
10. Add piece selection feedback (capture, verify)

### Phase 3: Animation
11. Move one piece by changing its position (capture before/after)
12. Add velocity and basic physics (capture multiple frames)
13. Add collision detection (verify with captures)

### Phase 4: Polish
14. Add page flipping for smooth animation
15. Add game logic (turns, win conditions)
16. Final testing with full gameplay

Each numbered step should have at least one `capture_hgr` call where you LOOK at the result.

---

## Remember

The AI can see images. The MCP server can capture screenshots. There is NO EXCUSE for shipping broken graphics code. If you didn't look at it, you didn't test it.
