#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
State management module for crawlers.
This module contains shared state variables used across different crawler modules.
"""

# Set of created folders
CREATED_FOLDERS = set()

# Counter for file naming
COUNTER = 1

# Current path for tracking dropdown selections
current_path = [] 