"""
Pytest configuration for memory-service tests.
Automatically configures sys.path to include src/ and project root.
"""

import os
import sys

# Add src/ directory to sys.path so 'from memory_service...' resolves correctly
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
# Add project root so 'from services.abstractions...' resolves correctly
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)
