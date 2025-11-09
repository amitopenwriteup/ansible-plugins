"""
Custom Callback Plugin: Monitor system resources during playbook execution
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    name: system_monitor
    type: stdout
    short_description: Monitor system resources during playbook execution
    version_added: "2.9"
    description:
        - Displays task execution with system resource monitoring
        - Shows CPU, memory, and disk usage
        - Tracks execution time for each task
    author: Your Name
    options:
        show_cpu:
            description: Show CPU usage
            default: True
            type: bool
        show_memory:
            description: Show memory usage
            default: True
            type: bool
        show_custom_stats:
            description: Show custom statistics
            default: True
            type: bool
"""

from ansible.plugins.callback import CallbackBase
from ansible import constants as C
from datetime import datetime
import time
import os

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class CallbackModule(CallbackBase):
    """
    Callback plugin to monitor system resources during playbook execution
    """
    
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'system_monitor'
    
    def __init__(self):
        super(CallbackModule, self).__init__()
        self.start_time = None
        self.task_start_time = None
        self.task_stats = {}
        self.play_stats = {}
    
    def v2_playbook_on_start(self, playbook):
        """Called when playbook starts"""
        self.start_time = time.time()
        
        self._display.banner("PLAYBOOK START")
        self._display.display(f"Playbook: {playbook._file_name}")
        self._display.display(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if HAS_PSUTIL:
            self._display_system_info()
        else:
            self._display.warning("psutil not installed - system monitoring disabled")
        
        self._display.display("")
    
    def v2_playbook_on_play_start(self, play):
        """Called when a play starts"""
        name = play.get_name().strip()
        if not name:
            name = "unnamed play"
        
        self._display.banner(f"PLAY [{name}]")
        
        if HAS_PSUTIL:
            self._display_resource_usage()
    
    def v2_playbook_on_task_start(self, task, is_conditional):
        """Called when a task starts"""
        self.task_start_time = time.time()
        
        task_name = task.get_name().strip()
        self._display.banner(f"TASK [{task_name}]")
    
    def v2_runner_on_ok(self, result):
        """Called when a task succeeds"""
        task_name = result._task.get_name().strip()
        host_name = result._host.get_name()
        
        # Calculate execution time
        exec_time = time.time() - self.task_start_time if self.task_start_time else 0
        
        # Store task statistics
        if task_name not in self.task_stats:
            self.task_stats[task_name] = {
                'ok': 0,
                'failed': 0,
                'changed': 0,
                'skipped': 0,
                'total_time': 0
            }
        
        self.task_stats[task_name]['ok'] += 1
        self.task_stats[task_name]['total_time'] += exec_time
        
        if result._result.get('changed', False):
            self.task_stats[task_name]['changed'] += 1
            status = self._colorize('changed', C.COLOR_CHANGED)
        else:
            status = self._colorize('ok', C.COLOR_OK)
        
        # Display result
        msg = f"{status}: [{host_name}] => {task_name}"
        
        if exec_time > 0:
            msg += f" ({exec_time:.2f}s)"
        
        self._display.display(msg)
        
        # Display resource usage for slow tasks
        if exec_time > 5 and HAS_PSUTIL:
            self._display_resource_usage(indent="  ")
    
    def v2_runner_on_failed(self, result, ignore_errors=False):
        """Called when a task fails"""
        task_name = result._task.get_name().strip()
        host_name = result._host.get_name()
        
        if task_name not in self.task_stats:
            self.task_stats[task_name] = {
                'ok': 0,
                'failed': 0,
                'changed': 0,
                'skipped': 0,
                'total_time': 0
            }
        
        self.task_stats[task_name]['failed'] += 1
        
        status = self._colorize('failed', C.COLOR_ERROR)
        
        msg = f"{status}: [{host_name}] => {task_name}"
        self._display.display(msg)
        
        # Display error message
        error_msg = result._result.get('msg', 'Unknown error')
        self._display.display(f"  Error: {error_msg}", color=C.COLOR_ERROR)
    
    def v2_runner_on_skipped(self, result):
        """Called when a task is skipped"""
        task_name = result._task.get_name().strip()
        host_name = result._host.get_name()
        
        if task_name not in self.task_stats:
            self.task_stats[task_name] = {
                'ok': 0,
                'failed': 0,
                'changed': 0,
                'skipped': 0,
                'total_time': 0
            }
        
        self.task_stats[task_name]['skipped'] += 1
        
        status = self._colorize('skipped', C.COLOR_SKIP)
        msg = f"{status}: [{host_name}] => {task_name}"
        self._display.display(msg)
    
    def v2_playbook_on_stats(self, stats):
        """Called when playbook ends - display summary"""
        self._display.banner("PLAY RECAP")
        
        hosts = sorted(stats.processed.keys())
        for host in hosts:
            summary = stats.summarize(host)
            
            msg = f"{host} : ok={summary['ok']} changed={summary['changed']}"
            msg += f" unreachable={summary['unreachable']} failed={summary['failures']}"
            msg += f" skipped={summary['skipped']} rescued={summary['rescued']}"
            msg += f" ignored={summary['ignored']}"
            
            self._display.display(msg)
        
        # Display task statistics
        if self.task_stats:
            self._display.banner("TASK STATISTICS")
            
            # Sort by total time
            sorted_tasks = sorted(
                self.task_stats.items(),
                key=lambda x: x[1]['total_time'],
                reverse=True
            )
            
            for task_name, stats in sorted_tasks:
                msg = f"{task_name}:"
                msg += f" ok={stats['ok']} failed={stats['failed']}"
                msg += f" changed={stats['changed']} skipped={stats['skipped']}"
                msg += f" time={stats['total_time']:.2f}s"
                self._display.display(msg)
        
        # Display total execution time
        if self.start_time:
            total_time = time.time() - self.start_time
            self._display.banner("SUMMARY")
            self._display.display(f"Total execution time: {total_time:.2f}s")
            
            if HAS_PSUTIL:
                self._display_resource_usage()
    
    def _display_system_info(self):
        """Display system information"""
        if not HAS_PSUTIL:
            return
        
        self._display.display("System Information:")
        self._display.display(f"  CPU Count: {psutil.cpu_count()}")
        self._display.display(f"  Total Memory: {self._format_bytes(psutil.virtual_memory().total)}")
        self._display.display(f"  Total Disk: {self._format_bytes(psutil.disk_usage('/').total)}")
    
    def _display_resource_usage(self, indent=""):
        """Display current resource usage"""
        if not HAS_PSUTIL:
            return
        
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        self._display.display(f"{indent}Resources:")
        self._display.display(f"{indent}  CPU: {cpu_percent}%")
        self._display.display(f"{indent}  Memory: {memory.percent}% ({self._format_bytes(memory.used)}/{self._format_bytes(memory.total)})")
        self._display.display(f"{indent}  Disk: {disk.percent}% ({self._format_bytes(disk.used)}/{self._format_bytes(disk.total)})")
    
    def _format_bytes(self, bytes_value):
        """Format bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def _colorize(self, text, color):
        """Colorize text"""
        if self._display.verbosity > 0:
            return f"\033[{color}m{text}\033[0m"
        return text

