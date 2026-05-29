#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dhcp_lease_parser.py

A script to parse ISC DHCP server leases for both IPv4 and IPv6,
correlate them with the live IPv6 neighbor cache, and display a
consolidated view of active clients.
"""

import re
import subprocess
from collections import defaultdict

# --- Configuration ---
DHCP4_LEASES_FILE = '/var/lib/dhcp/dhcpd.leases'
DHCP6_LEASES_FILE = '/var/lib/dhcp/dhcpd6.leases'

def parse_dhcpv4_leases(lease_file):
    """
    Parses the dhcpd.leases file to find active IPv4 leases.

    Returns:
        A dictionary mapping MAC addresses to a dict of lease info.
        e.g., {'mac': {'ipv4': 'ip_addr', 'hostname': 'client_host'}}
    """
    try:
        with open(lease_file, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Warning: IPv4 lease file not found at {lease_file}")
        return {}

    # This regex is complex. It captures the last active lease for each IP.
    # It finds all leases, then they are processed to find the last active one.
    leases = {}
    
    # A simpler, line-by-line parser is more robust than a single monster regex.
    current_lease = {}
    for line in content.splitlines():
        line = line.strip()

        if line.startswith('lease'):
            # When a new lease block starts, save the previous one if valid
            if current_lease.get('ip') and current_lease.get('mac') and current_lease.get('state') == 'active':
                mac = current_lease['mac']
                if mac not in leases:
                    leases[mac] = {'ipv4_list': set(), 'hostname': '(unknown)'}
                leases[mac]['ipv4_list'].add(current_lease['ip'])
                if current_lease.get('hostname'):
                    leases[mac]['hostname'] = current_lease['hostname']
            
            # Start a new lease
            current_lease = {'ip': line.split(' ')[1]}

        elif line.startswith('binding state'):
            current_lease['state'] = line.split(' ')[2].strip(';')

        elif line.startswith('hardware ethernet'):
            current_lease['mac'] = line.split(' ')[2].strip(';')

        elif line.startswith('client-hostname'):
            match = re.search(r'"(.*?)"', line)
            if match:
                current_lease['hostname'] = match.group(1)
        
        elif line.startswith('}'):
             # End of lease block, save if valid
            if current_lease.get('ip') and current_lease.get('mac') and current_lease.get('state') == 'active':
                mac = current_lease['mac']
                if mac not in leases:
                    leases[mac] = {'ipv4_list': set(), 'hostname': '(unknown)'}
                leases[mac]['ipv4_list'].add(current_lease['ip'])
                if current_lease.get('hostname'):
                    leases[mac]['hostname'] = current_lease['hostname']
            current_lease = {}


    return leases

def get_ipv6_neighbors():
    """
    Runs 'ip -6 neigh show' and parses the output.

    Returns:
        A dictionary mapping MAC addresses to a list of their IPv6 addresses.
    """
    clients = defaultdict(lambda: {'ipv6_list': set()})
    try:
        # Execute the command
        result = subprocess.run(
            ['ip', '-6', 'neigh', 'show'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the output
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            # Ignore incomplete lines or non-routable addresses
            if len(parts) < 5 or 'fe80::' in parts[0]:
                continue
            
            ipv6_addr = parts[0]
            mac_addr = parts[4]
            clients[mac_addr]['ipv6_list'].add(ipv6_addr)
            
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Could not execute 'ip -6 neigh': {e}")
        return {}
        
    return clients

def main():
    """Main function to orchestrate parsing and printing."""
    
    print("Parsing DHCP leases and IPv6 neighbor cache...")
    
    ipv4_clients = parse_dhcpv4_leases(DHCP4_LEASES_FILE)
    ipv6_clients = get_ipv6_neighbors()
    
    # --- Data Correlation ---
    # Use the IPv4 client list as the master list, as it often has hostnames
    master_clients = ipv4_clients

    for mac, ipv6_data in ipv6_clients.items():
        if mac in master_clients:
            # If we know this client from IPv4, just add its IPv6 address
            master_clients[mac].setdefault('ipv6_list', set()).update(ipv6_data['ipv6_list'])
        else:
            # If this is a new client (IPv6-only), add it to the list
            master_clients[mac] = {
                'ipv4_list': set(),
                'hostname': '(unknown)',
                'ipv6_list': ipv6_data['ipv6_list']
            }

    # --- Print Results ---
    print("\n--- Consolidated Active Clients ---")
    
    # Header
    print(f"{'MAC Address':<20} {'Hostname':<20} {'IPv4 Address(es)':<25} {'IPv6 Address(es) (from NDP)':<45}")
    print(f"{'-'*18:<20} {'-'*18:<20} {'-'*23:<25} {'-'*43:<45}")

    if not master_clients:
        print("No active clients found.")
        return

    for mac, data in sorted(master_clients.items()):
        ipv4_str = ', '.join(sorted(data.get('ipv4_list', []))) or 'N/A'
        ipv6_str = ', '.join(sorted(data.get('ipv6_list', []))) or 'N/A'
        hostname = data.get('hostname', '(unknown)')
        
        print(f"{mac:<20} {hostname:<20} {ipv4_str:<25} {ipv6_str:<45}")

if __name__ == '__main__':
    main()
