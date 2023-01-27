#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2023, MAPP <sergey.polyakov@mapp.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = r'''
---
module: ringparams_facts
short_description: Return C(Query) RX/TX ring parameters of network interfaces information as fact data
description:
     - Return Query RX/TX ring parameters for network interfaces if such informatio available.
version_added: "2.14.0"
requirements: ["Installed ethtool package"]
options:
  interfaces:
    required: false
    type: list
    elements: str
    default: []
    description:
      - Network interface names
    aliases: [name]
author:
  - Sergey Polyakov (@3hedgehogs)
'''

EXAMPLES = r'''
- name: Populate network interface ringparameters facts for interfaces eno3 and eno4
  mapp.mta_collection.ringparams_facts:
    interfaces:
      - eno3
      - eno4
    register: result

- name: Print service facts
  ansible.builtin.debug:
    var: ansible_facts.ringparams
'''

RETURN = r'''
ansible_facts:
  description: Facts to add to ansible_facts about the set of interfaces
  returned: always
  type: complex
  contains:
    ringparams:
      description: List of the dict with ring parameters.
      returned: always
      type: complex
      contains:
        interface:
          description:
          - Interface name
          returned: always
          type: str
          sample: eno1
        supported:
          description:
          - Show if interface supports ring parameters or not
          returned: always
          type: bool
          sample: true
        parameters:
          description: dict of ring parameters for the interface (see C(ethtool -g) output)
          returned: always
          type: complex
          contains:
            current:
               description: dict of ring parameters for the current values in interface
               returned: on success, when C(supported) is true
               type: complex
               contains:
                 RX:
                   description: RX value
                   returned: on success, when C(supported) is true
                   type: str
                 TX:
                   description: TX value
                   returned: on success, when C(supported) is true
                   type: str
            preset:
               description: dict of ring parameters for the preset values in interface
               type: complex
               contains:
                 RX:
                   description: RX value
                   returned: on success, when C(supported) is true
                   type: str
                 TX:
                   description: TX value
                   returned: on success, when C(supported) is true
                   type: str
'''

import os
import shutil
from shlex import quote
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.locale import get_best_parsable_locale


def get_interfaces(module):
    ''' Return list of network interfaces excluding lo '''

    list_interfaces = []
    if os.path.isfile('/proc/net/dev'):
        rc, stdout, stderr = module.run_command(
            "/usr/bin/cat /proc/net/dev | /usr/bin/tail -n +3 | /usr/bin/awk -F: '{ print $1 }'",
            use_unsafe_shell=True
        )
        if rc == 0:
            for line in stdout.strip().splitlines():
                intf = line.strip()
                if intf != 'lo':
                    list_interfaces.append(intf)
        else:
            stderr = stderr.replace("\n", ".")
            module.warn(f'Unable to fetch list of network interfaces: {stderr}')

    return list_interfaces


def main():
    arg_spec = dict(
        interfaces=dict(required=False, type='list', elements='str', aliases=['name'], default=[]),
    )
    module = AnsibleModule(
        argument_spec=arg_spec,
        supports_check_mode=True
    )
    locale = get_best_parsable_locale(module)
    module.run_command_environ_update = dict(LANG=locale, LC_ALL=locale)
    list_interfaces = module.params['interfaces']
    result = {}
    result['network_interfaces'] = list_interfaces
    values = {}
    ringparams = []

    exe = shutil.which('ethtool')
    if exe is None:
        module.fail_json(msg='Could not find ethtool executable', **result)

    # If list is empty = will try to find all interfaces except 'lo'
    if not list_interfaces:
        list_interfaces = get_interfaces(module)

    for interface in list_interfaces:
        values[interface] = {}
        values[interface]['current'] = {}
        values[interface]['preset'] = {}

        rc, stdout, stderr = module.run_command(f"{exe} -g " + quote(interface))
        if rc != 0:
            stderr = stderr.replace("\n", ".")
            module.warn(f'Unable to run ethtool for {interface}: {stderr}')
            ringparams.append({'interface': interface,
                               'supported': False,
                               'parameters': values[interface],
                               'msg': 'Failed to find ringparams'})
        else:
            pre = False
            current = False
            preSetRX = 0
            preSetTX = 0
            currentRX = 0
            currentTX = 0
            if rc == 0:
                for line in stdout.strip().splitlines():
                    l = line.strip()
                    if l == 'Pre-set maximums:':
                        current = False
                        pre = True
                    if l == 'Current hardware settings:':
                        current = True
                        pre = False
                    if l.startswith('RX:'):
                        if current:
                            currentRX = l.split(':')[1].strip()
                            values[interface]['current']['RX'] = currentRX
                        if pre:
                            preSetRX = l.split(':')[1].strip()
                            values[interface]['preset']['RX'] = preSetRX
                    if l.startswith('TX:'):
                        if current:
                            currentTX = l.split(':')[1].strip()
                            values[interface]['current']['TX'] = currentTX
                        if pre:
                            preSetTX = l.split(':')[1].strip()
                            values[interface]['preset']['TX'] = preSetTX

                ringparams.append({'interface': interface, 'supported': True, 'parameters': values[interface]})

    results = dict(ansible_facts=dict(ringparams=ringparams))
    module.exit_json(**results)


if __name__ == '__main__':
    main()
