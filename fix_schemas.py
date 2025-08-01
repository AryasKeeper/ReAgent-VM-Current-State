#!/usr/bin/env python3
"""
Fix Weaviate Schema Index Configurations

Removes deprecated indexInverted fields and fixes property indexing
for compatibility with Weaviate v1.21.2
"""

import re
import sys
from pathlib import Path

def fix_schema_file():
    """Fix the schemas.py file by removing deprecated indexInverted."""
    
    schemas_path = Path("src/core/vector_db/schemas.py")
    
    # Read the file
    with open(schemas_path, 'r') as f:
        content = f.read()
    
    # Remove indexInverted lines
    # Pattern to match lines with "indexInverted": True or False
    content = re.sub(r'\s*"indexInverted":\s*(True|False),?\n', '', content)
    
    # Clean up any double commas that might result
    content = re.sub(r',\s*,', ',', content)
    
    # Clean up trailing commas before closing braces
    content = re.sub(r',(\s*\})', r'\1', content)
    
    # Write back
    with open(schemas_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed schema file: {schemas_path}")

if __name__ == "__main__":
    fix_schema_file()