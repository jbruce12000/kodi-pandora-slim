#!/usr/bin/env python3
"""
Build script to create plugin.audio.pandora.zip from source directory
"""

import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime

def generate_build_version():
    """Generate a unique build ID based on timestamp"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def create_version_file(source_dir, build_id):
    """Create a version.py file with build information"""
    version_content = f'''"""Auto-generated build version file"""
BUILD_ID = "{build_id}"
BUILD_DATE = "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"
PLUGIN_VERSION = "3.0.0"
'''
    version_file = Path(source_dir) / "resources" / "lib" / "version.py"
    version_file.write_text(version_content)
    return version_file

def build_plugin(source_dir="plugin.audio.pandora", output_name="plugin.audio.pandora.zip", build_id=None):
    """
    Create a zip file of the plugin directory.
    
    Args:
        source_dir: Path to the plugin source directory
        output_name: Name of the output zip file
    """
    source_path = Path(source_dir)
    
    # Verify source directory exists
    if not source_path.exists():
        print(f"Error: Source directory '{source_dir}' not found")
        return False
    
    if not source_path.is_dir():
        print(f"Error: '{source_dir}' is not a directory")
        return False
    
    # Check for required files
    required_files = ["addon.xml", "default.py"]
    for req_file in required_files:
        if not (source_path / req_file).exists():
            print(f"Error: Required file '{req_file}' not found in {source_dir}")
            return False
    
    try:
        # Create zip file
        with zipfile.ZipFile(output_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the source directory
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = Path(root) / file
                    # Calculate the archive name (relative path from current directory)
                    arcname = file_path.relative_to('.')
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
        
        output_size = os.path.getsize(output_name)
        print(f"\n✓ Successfully created '{output_name}' ({output_size:,} bytes)")
        return True
    
    except Exception as e:
        print(f"Error creating zip file: {e}")
        return False

def main():
    # Determine working directory
    cwd = Path.cwd()
    print(f"Building plugin from: {cwd}")
    
    # Check if we're in the right directory
    if not Path("plugin.audio.pandora").exists():
        print("Error: plugin.audio.pandora directory not found in current directory")
        print(f"Current directory: {cwd}")
        print("Please run this script from the pandora directory")
        return 1
    
    # Generate build ID
    build_id = generate_build_version()
    print(f"Build ID: {build_id}\n")
    
    # Create version file
    print("Generating version file...")
    create_version_file("plugin.audio.pandora", build_id)
    print(f"  Created: version.py\n")
    
    print("Building plugin.audio.pandora.zip...\n")
    
    success = build_plugin(build_id=build_id)
    
    if success:
        print(f"\n✓ Build complete! Build ID: {build_id}")
        print("Done!")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
