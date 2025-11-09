"""
Custom Connection Plugin: Enhanced SSH with logging
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    name: custom_ssh
    short_description: Custom SSH connection with enhanced logging
    description:
        - SSH connection plugin with detailed logging
        - Logs all commands executed
        - Tracks connection statistics
    author: Your Name
    version_added: "2.9"
    options:
        remote_addr:
            description: Address of the remote target
            default: inventory_hostname
            vars:
                - name: ansible_host
                - name: ansible_ssh_host
        remote_user:
            description: User to login as
            vars:
                - name: ansible_user
                - name: ansible_ssh_user
        log_commands:
            description: Log all commands executed
            type: bool
            default: True
            vars:
                - name: ansible_ssh_log_commands
"""

from ansible.plugins.connection.ssh import Connection as SSHConnection
from ansible.utils.display import Display
import os
import time
from datetime import datetime

display = Display()

class Connection(SSHConnection):
    """
    Custom SSH connection plugin with enhanced logging
    
    Extends the standard SSH connection to add:
    - Command logging
    - Execution time tracking
    - Connection statistics
    """
    
    transport = 'custom_ssh'
    
    def __init__(self, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        
        self.log_commands = True
        self.log_file = '/tmp/ansible_custom_ssh.log'
        self.command_count = 0
        self.total_exec_time = 0
        self.connection_start = None
    
    def _connect(self):
        """Establish SSH connection with logging"""
        self.connection_start = time.time()
        
        display.vvv(f"custom_ssh: Connecting to {self._play_context.remote_addr}", 
                    host=self._play_context.remote_addr)
        
        self._log_event(f"Connecting to {self._play_context.remote_addr} as {self._play_context.remote_user}")
        
        # Call parent connect method
        result = super(Connection, self)._connect()
        
        connect_time = time.time() - self.connection_start
        self._log_event(f"Connected successfully in {connect_time:.2f}s")
        
        return result
    
    def exec_command(self, cmd, in_data=None, sudoable=True):
        """
        Execute a command on the remote host with logging
        
        Args:
            cmd: Command to execute
            in_data: Data to send to stdin
            sudoable: Whether command can be run with sudo
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        self.command_count += 1
        start_time = time.time()
        
        display.vvv(f"custom_ssh: Executing command: {cmd}", 
                    host=self._play_context.remote_addr)
        
        self._log_event(f"Executing command #{self.command_count}: {cmd}")
        
        # Execute command using parent method
        returncode, stdout, stderr = super(Connection, self).exec_command(cmd, in_data, sudoable)
        
        exec_time = time.time() - start_time
        self.total_exec_time += exec_time
        
        # Log results
        log_msg = f"Command #{self.command_count} completed in {exec_time:.2f}s - "
        log_msg += f"RC: {returncode}"
        
        if returncode != 0:
            log_msg += f" | STDERR: {stderr[:200]}"  # Log first 200 chars of error
        
        self._log_event(log_msg)
        
        display.vvv(f"custom_ssh: Command completed - RC: {returncode}, Time: {exec_time:.2f}s",
                    host=self._play_context.remote_addr)
        
        return returncode, stdout, stderr
    
    def put_file(self, in_path, out_path):
        """
        Transfer a file to the remote host with logging
        
        Args:
            in_path: Local file path
            out_path: Remote file path
        """
        start_time = time.time()
        
        display.vvv(f"custom_ssh: Copying {in_path} to {out_path}",
                    host=self._play_context.remote_addr)
        
        file_size = os.path.getsize(in_path) if os.path.exists(in_path) else 0
        self._log_event(f"Uploading file: {in_path} -> {out_path} ({file_size} bytes)")
        
        # Transfer file using parent method
        super(Connection, self).put_file(in_path, out_path)
        
        transfer_time = time.time() - start_time
        self._log_event(f"Upload completed in {transfer_time:.2f}s")
        
        display.vvv(f"custom_ssh: File copied in {transfer_time:.2f}s",
                    host=self._play_context.remote_addr)
    
    def fetch_file(self, in_path, out_path):
        """
        Fetch a file from the remote host with logging
        
        Args:
            in_path: Remote file path
            out_path: Local file path
        """
        start_time = time.time()
        
        display.vvv(f"custom_ssh: Fetching {in_path} to {out_path}",
                    host=self._play_context.remote_addr)
        
        self._log_event(f"Downloading file: {in_path} -> {out_path}")
        
        # Fetch file using parent method
        super(Connection, self).fetch_file(in_path, out_path)
        
        transfer_time = time.time() - start_time
        file_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        self._log_event(f"Download completed in {transfer_time:.2f}s ({file_size} bytes)")
        
        display.vvv(f"custom_ssh: File fetched in {transfer_time:.2f}s",
                    host=self._play_context.remote_addr)
    
    def close(self):
        """Close connection with summary logging"""
        if self.connection_start:
            total_time = time.time() - self.connection_start
            
            summary = f"Connection closed - Commands: {self.command_count}, "
            summary += f"Total exec time: {self.total_exec_time:.2f}s, "
            summary += f"Total session time: {total_time:.2f}s"
            
            self._log_event(summary)
            
            display.vvv(f"custom_ssh: {summary}",
                       host=self._play_context.remote_addr)
        
        super(Connection, self).close()
    
    def _log_event(self, message):
        """
        Log event to file
        
        Args:
            message: Message to log
        """
        if not self.log_commands:
            return
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            host = self._play_context.remote_addr
            log_entry = f"[{timestamp}] {host} - {message}\n"
            
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            display.warning(f"custom_ssh: Failed to log event: {e}")

