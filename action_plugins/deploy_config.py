"""
Custom Action Plugin: Deploy configuration with validation
Usage: deploy_config module in playbooks
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleActionFail
from ansible.utils.display import Display
import os
import tempfile
import hashlib

display = Display()

class ActionModule(ActionBase):
    """
    Action plugin to deploy configuration files with validation
    
    This plugin:
    1. Validates config file on control node
    2. Backs up existing config on remote host
    3. Deploys new config
    4. Validates deployment
    5. Rolls back if validation fails
    """
    
    TRANSFERS_FILES = True
    
    def run(self, tmp=None, task_vars=None):
        """
        Main execution method for action plugin
        
        Args:
            tmp: Temporary directory path
            task_vars: Available task variables
        
        Returns:
            Dictionary with results
        """
        if task_vars is None:
            task_vars = dict()
        
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect
        
        # Get module arguments
        source = self._task.args.get('src', None)
        dest = self._task.args.get('dest', None)
        validate_cmd = self._task.args.get('validate', None)
        backup = self._task.args.get('backup', True)
        owner = self._task.args.get('owner', None)
        group = self._task.args.get('group', None)
        mode = self._task.args.get('mode', None)
        
        # Validate required arguments
        if source is None:
            result['failed'] = True
            result['msg'] = "src is required"
            return result
        
        if dest is None:
            result['failed'] = True
            result['msg'] = "dest is required"
            return result
        
        display.vvv(f"deploy_config: Deploying {source} to {dest}")
        
        try:
            # Step 1: Find source file on control node
            source = self._find_needle('files', source)
            display.vvv(f"deploy_config: Source file found at {source}")
            
            # Step 2: Calculate source file checksum
            with open(source, 'rb') as f:
                source_checksum = hashlib.md5(f.read()).hexdigest()
            
            display.vvv(f"deploy_config: Source checksum: {source_checksum}")
            
            # Step 3: Check if destination file exists and get its checksum
            stat_result = self._execute_module(
                module_name='stat',
                module_args={'path': dest},
                task_vars=task_vars
            )
            
            dest_exists = stat_result.get('stat', {}).get('exists', False)
            dest_checksum = stat_result.get('stat', {}).get('checksum', None)
            
            # Step 4: Backup existing file if requested
            backup_file = None
            if backup and dest_exists:
                display.vvv(f"deploy_config: Backing up {dest}")
                
                backup_result = self._execute_module(
                    module_name='copy',
                    module_args={
                        'src': dest,
                        'dest': f"{dest}.backup",
                        'remote_src': True
                    },
                    task_vars=task_vars
                )
                
                if backup_result.get('failed'):
                    result['failed'] = True
                    result['msg'] = f"Backup failed: {backup_result.get('msg')}"
                    return result
                
                backup_file = f"{dest}.backup"
                result['backup_file'] = backup_file
            
            # Step 5: Copy file to remote host
            display.vvv(f"deploy_config: Copying to {dest}")
            
            copy_args = {
                'src': source,
                'dest': dest,
            }
            
            if owner:
                copy_args['owner'] = owner
            if group:
                copy_args['group'] = group
            if mode:
                copy_args['mode'] = mode
            
            copy_result = self._execute_module(
                module_name='copy',
                module_args=copy_args,
                task_vars=task_vars
            )
            
            if copy_result.get('failed'):
                result['failed'] = True
                result['msg'] = f"Copy failed: {copy_result.get('msg')}"
                return result
            
            result['changed'] = copy_result.get('changed', False)
            result['dest'] = dest
            result['checksum'] = source_checksum
            
            # Step 6: Validate deployed configuration
            if validate_cmd:
                display.vvv(f"deploy_config: Validating with: {validate_cmd}")
                
                # Replace %s with destination file path
                validate_cmd = validate_cmd.replace('%s', dest)
                
                validate_result = self._execute_module(
                    module_name='command',
                    module_args={'_raw_params': validate_cmd},
                    task_vars=task_vars
                )
                
                if validate_result.get('rc', 0) != 0:
                    # Validation failed - rollback
                    display.warning(f"deploy_config: Validation failed, rolling back")
                    
                    if backup_file:
                        self._execute_module(
                            module_name='copy',
                            module_args={
                                'src': backup_file,
                                'dest': dest,
                                'remote_src': True
                            },
                            task_vars=task_vars
                        )
                    
                    result['failed'] = True
                    result['msg'] = f"Validation failed: {validate_result.get('stderr', 'Unknown error')}"
                    result['validation_output'] = validate_result.get('stdout', '')
                    return result
                
                result['validation'] = 'passed'
                result['validation_output'] = validate_result.get('stdout', '')
            
            # Step 7: Remove backup if everything succeeded and not needed
            if backup_file and not backup:
                self._execute_module(
                    module_name='file',
                    module_args={'path': backup_file, 'state': 'absent'},
                    task_vars=task_vars
                )
            
            result['msg'] = f"Successfully deployed {source} to {dest}"
            display.vvv(f"deploy_config: Deployment successful")
            
        except AnsibleActionFail as e:
            result['failed'] = True
            result['msg'] = str(e)
        except Exception as e:
            result['failed'] = True
            result['msg'] = f"Unexpected error: {str(e)}"
        
        return result

