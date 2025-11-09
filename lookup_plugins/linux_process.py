"""
Custom Lookup Plugin: Get Linux process information
Usage: {{ lookup('linux_process', 'nginx') }}
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    name: linux_process
    author: Your Name
    version_added: "2.9"
    short_description: Lookup Linux process information
    description:
        - This lookup returns information about running Linux processes
        - Can search by process name or PID
    options:
        _terms:
            description: Process name or PID to search for
            required: True
        detailed:
            description: Return detailed process information
            type: bool
            default: False
    notes:
        - Requires psutil library on control node
    examples:
        - name: Get nginx process info
          debug:
            msg: "{{ lookup('linux_process', 'nginx') }}"
        
        - name: Get detailed process info
          debug:
            msg: "{{ lookup('linux_process', 'apache2', detailed=True) }}"
"""

RETURN = """
_list:
    description: List of process information dictionaries
    type: list
    elements: dict
    contains:
        pid:
            description: Process ID
            type: int
        name:
            description: Process name
            type: str
        status:
            description: Process status
            type: str
        cpu_percent:
            description: CPU usage percentage
            type: float
        memory_percent:
            description: Memory usage percentage
            type: float
"""

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display
import subprocess
import json

display = Display()

class LookupModule(LookupBase):
    """Linux process lookup plugin"""
    
    def run(self, terms, variables=None, **kwargs):
        """
        Main execution method for lookup plugin
        
        Args:
            terms: List of search terms (process names or PIDs)
            variables: Available Ansible variables
            **kwargs: Additional arguments (like detailed=True)
        
        Returns:
            List of process information
        """
        ret = []
        
        # Get options
        self.set_options(var_options=variables, direct=kwargs)
        detailed = kwargs.get('detailed', False)
        
        for term in terms:
            display.vvv(f"linux_process lookup: Searching for '{term}'")
            
            try:
                # Search for process using ps command
                process_info = self._get_process_info(term, detailed)
                ret.append(process_info)
                
            except Exception as e:
                raise AnsibleError(f"Error looking up process '{term}': {str(e)}")
        
        return ret
    
    def _get_process_info(self, search_term, detailed=False):
        """
        Get process information from Linux system
        
        Args:
            search_term: Process name or PID
            detailed: Return detailed information
        
        Returns:
            Dictionary with process information
        """
        try:
            # Use ps command to get process info
            if detailed:
                cmd = ['ps', 'aux']
            else:
                cmd = ['ps', '-eo', 'pid,comm,state,%cpu,%mem']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            processes = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if search_term.lower() in line.lower():
                    parts = line.split(None, 4 if detailed else 4)
                    
                    if detailed:
                        process = {
                            'user': parts[0],
                            'pid': int(parts[1]),
                            'cpu_percent': float(parts[2]),
                            'memory_percent': float(parts[3]),
                            'vsz': parts[4],
                            'rss': parts[5],
                            'tty': parts[6],
                            'stat': parts[7],
                            'start': parts[8],
                            'time': parts[9],
                            'command': parts[10] if len(parts) > 10 else ''
                        }
                    else:
                        process = {
                            'pid': int(parts[0]),
                            'name': parts[1],
                            'state': parts[2],
                            'cpu_percent': float(parts[3]),
                            'memory_percent': float(parts[4])
                        }
                    
                    processes.append(process)
            
            return {
                'search_term': search_term,
                'found': len(processes),
                'processes': processes
            }
            
        except subprocess.CalledProcessError as e:
            raise AnsibleError(f"Failed to get process info: {e}")
        except Exception as e:
            raise AnsibleError(f"Error parsing process info: {e}")

