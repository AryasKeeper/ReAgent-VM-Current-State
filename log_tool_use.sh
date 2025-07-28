#!/bin/bash

# Where to store the tool usage logs
LOG_FILE="./subagent_hooks.log"

# Read Claude's input payload (JSON)
INPUT=$(cat)

# Extract the tool name and tool_use_id from JSON
TOOL_NAME=$(echo "$INPUT" | grep -o '"tool_name": *"[^"]*"' | cut -d'"' -f4)
TOOL_USE_ID=$(echo "$INPUT" | grep -o '"tool_use_id": *"[^"]*"' | cut -d'"' -f4)

# Log it
echo "[PostToolUse] Tool: $TOOL_NAME | ID: $TOOL_USE_ID | Time: $(date)" >> $LOG_FILE
echo "$INPUT" >> $LOG_FILE
echo "------" >> $LOG_FILE
