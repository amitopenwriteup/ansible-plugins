"""
Custom Filter Plugin: Linux system utilities
Usage: {{ some_value | format_bytes }}
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    name: linux_utils
    author: Your Name
    version_added: "2.9"
    short_description: Linux system utility filters
    description:
        - Collection of filters for Linux system administration
        - Includes file size formatting, permission conversion, etc.
    filters:
        format_bytes:
            description: Format bytes into human-readable format
            type: int
            required: True
        
        octal_to_symbolic:
            description: Convert octal permissions to symbolic (755 -> rwxr-xr-x)
            type: string
            required: True
        
        symbolic_to_octal:
            description: Convert symbolic permissions to octal
            type: string
            required: True
        
        parse_uptime:
            description: Parse Linux uptime string
            type: string
            required: True
"""

import re
from ansible.errors import AnsibleFilterError

def format_bytes(bytes_value, precision=2):
    """
    Convert bytes to human-readable format
    
    Args:
        bytes_value: Number of bytes
        precision: Decimal precision
    
    Returns:
        Formatted string (e.g., "1.5 GB")
    
    Example:
        {{ 1073741824 | format_bytes }}  => "1.00 GB"
    """
    try:
        bytes_value = float(bytes_value)
    except (ValueError, TypeError):
        raise AnsibleFilterError(f"format_bytes: Invalid input '{bytes_value}'")
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    
    while bytes_value >= 1024.0 and unit_index < len(units) - 1:
        bytes_value /= 1024.0
        unit_index += 1
    
    return f"{bytes_value:.{precision}f} {units[unit_index]}"

def octal_to_symbolic(octal_perm):
    """
    Convert octal permissions to symbolic format
    
    Args:
        octal_perm: Octal permission string (e.g., "755", "0644")
    
    Returns:
        Symbolic permission string (e.g., "rwxr-xr-x")
    
    Example:
        {{ "755" | octal_to_symbolic }}  => "rwxr-xr-x"
    """
    try:
        # Remove leading '0' if present
        octal_perm = str(octal_perm).lstrip('0')
        if not octal_perm:
            octal_perm = '0'
        
        # Convert to integer
        perm_int = int(octal_perm, 8)
        
        # Permission bits
        perms = []
        for shift in [6, 3, 0]:  # Owner, Group, Other
            bits = (perm_int >> shift) & 0o7
            perm_str = ''
            perm_str += 'r' if bits & 0o4 else '-'
            perm_str += 'w' if bits & 0o2 else '-'
            perm_str += 'x' if bits & 0o1 else '-'
            perms.append(perm_str)
        
        return ''.join(perms)
        
    except (ValueError, TypeError):
        raise AnsibleFilterError(f"octal_to_symbolic: Invalid octal '{octal_perm}'")

def symbolic_to_octal(symbolic_perm):
    """
    Convert symbolic permissions to octal format
    
    Args:
        symbolic_perm: Symbolic permission string (e.g., "rwxr-xr-x")
    
    Returns:
        Octal permission string (e.g., "755")
    
    Example:
        {{ "rwxr-xr-x" | symbolic_to_octal }}  => "755"
    """
    if len(symbolic_perm) != 9:
        raise AnsibleFilterError(
            f"symbolic_to_octal: Expected 9 characters, got {len(symbolic_perm)}"
        )
    
    octal_value = 0
    
    # Owner permissions
    if symbolic_perm[0] == 'r': octal_value += 0o400
    if symbolic_perm[1] == 'w': octal_value += 0o200
    if symbolic_perm[2] == 'x': octal_value += 0o100
    
    # Group permissions
    if symbolic_perm[3] == 'r': octal_value += 0o40
    if symbolic_perm[4] == 'w': octal_value += 0o20
    if symbolic_perm[5] == 'x': octal_value += 0o10
    
    # Other permissions
    if symbolic_perm[6] == 'r': octal_value += 0o4
    if symbolic_perm[7] == 'w': octal_value += 0o2
    if symbolic_perm[8] == 'x': octal_value += 0o1
    
    return oct(octal_value)[2:]

def parse_uptime(uptime_string):
    """
    Parse Linux uptime command output
    
    Args:
        uptime_string: Output from uptime command
    
    Returns:
        Dictionary with parsed uptime information
    
    Example:
        {{ uptime_output | parse_uptime }}
    """
    result = {
        'current_time': None,
        'uptime_days': 0,
        'uptime_hours': 0,
        'uptime_minutes': 0,
        'users': 0,
        'load_avg_1': 0.0,
        'load_avg_5': 0.0,
        'load_avg_15': 0.0
    }
    
    try:
        # Parse current time
        time_match = re.search(r'(\d+:\d+:\d+)', uptime_string)
        if time_match:
            result['current_time'] = time_match.group(1)
        
        # Parse uptime
        days_match = re.search(r'(\d+)\s+days?', uptime_string)
        if days_match:
            result['uptime_days'] = int(days_match.group(1))
        
        time_match = re.search(r'(\d+):(\d+),', uptime_string)
        if time_match:
            result['uptime_hours'] = int(time_match.group(1))
            result['uptime_minutes'] = int(time_match.group(2))
        
        # Parse users
        users_match = re.search(r'(\d+)\s+users?', uptime_string)
        if users_match:
            result['users'] = int(users_match.group(1))
        
        # Parse load average
        load_match = re.search(r'load average:\s+([\d.]+),\s+([\d.]+),\s+([\d.]+)', uptime_string)
        if load_match:
            result['load_avg_1'] = float(load_match.group(1))
            result['load_avg_5'] = float(load_match.group(2))
            result['load_avg_15'] = float(load_match.group(3))
        
        return result
        
    except Exception as e:
        raise AnsibleFilterError(f"parse_uptime: Error parsing '{uptime_string}': {e}")

def extract_ip_addresses(text):
    """
    Extract all IPv4 addresses from text
    
    Args:
        text: Text to search
    
    Returns:
        List of IP addresses
    
    Example:
        {{ log_content | extract_ip_addresses }}
    """
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    return re.findall(ip_pattern, str(text))

def calculate_disk_usage_percent(used, total):
    """
    Calculate disk usage percentage
    
    Args:
        used: Used space in bytes
        total: Total space in bytes
    
    Returns:
        Usage percentage
    
    Example:
        {{ used_space | calculate_disk_usage_percent(total_space) }}
    """
    try:
        used = float(used)
        total = float(total)
        if total == 0:
            return 0.0
        return round((used / total) * 100, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        raise AnsibleFilterError("calculate_disk_usage_percent: Invalid input")

class FilterModule(object):
    """Ansible filter plugin for Linux utilities"""
    
    def filters(self):
        """Return dictionary of filter functions"""
        return {
            'format_bytes': format_bytes,
            'octal_to_symbolic': octal_to_symbolic,
            'symbolic_to_octal': symbolic_to_octal,
            'parse_uptime': parse_uptime,
            'extract_ip_addresses': extract_ip_addresses,
            'calculate_disk_usage_percent': calculate_disk_usage_percent
        }

