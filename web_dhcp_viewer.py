#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
web_dhcp_viewer.py

A Flask web application to display active DHCP leases.
"""

import re
import subprocess
from collections import defaultdict
from flask import Flask, render_template, request

# --- Configuration ---
DHCP4_LEASES_FILE = '/var/lib/dhcp/dhcpd.leases'
DHCP6_LEASES_FILE = '/var/lib/dhcp/dhcpd6.leases'

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Core Parsing Logic ---

def parse_dhcpv4_leases(lease_file):
    """Parses the dhcpd.leases file to find active IPv4 leases."""
    try:
        with open(lease_file, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Warning: IPv4 lease file not found at {lease_file}")
        return {}
    
    leases = {}
    current_lease = {}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('lease'):
            if current_lease.get('ip') and current_lease.get('mac') and current_lease.get('state') == 'active':
                mac = current_lease['mac']
                if mac not in leases:
                    leases[mac] = {'ipv4_list': set(), 'hostname': '(unknown)'}
                leases[mac]['ipv4_list'].add(current_lease['ip'])
                if current_lease.get('hostname'):
                    leases[mac]['hostname'] = current_lease['hostname']
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
    """Runs 'ip -6 neigh show' and parses the output."""
    clients = defaultdict(lambda: {'ipv6_list': set()})
    try:
        result = subprocess.run(
            ['ip', '-6', 'neigh', 'show'],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) < 5 or 'fe80::' in parts[0]:
                continue
            ipv6_addr = parts[0]
            mac_addr = parts[4]
            clients[mac_addr]['ipv6_list'].add(ipv6_addr)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Could not execute 'ip -6 neigh': {e}")
        return {}
    return clients

def get_consolidated_clients():
    """Combines all data sources to create a master client list."""
    ipv4_clients = parse_dhcpv4_leases(DHCP4_LEASES_FILE)
    ipv6_clients = get_ipv6_neighbors()
    master_clients = ipv4_clients
    for mac, ipv6_data in ipv6_clients.items():
        if mac in master_clients:
            master_clients[mac].setdefault('ipv6_list', set()).update(ipv6_data['ipv6_list'])
        else:
            master_clients[mac] = {
                'ipv4_list': set(),
                'hostname': '(unknown)',
                'ipv6_list': ipv6_data['ipv6_list']
            }
    return dict(sorted(master_clients.items()))

# --- Flask Routes ---

@app.route('/')
def index():
    """Main route to display the DHCP client table."""
    search_query = request.args.get('search', '').strip().lower()
    all_clients = get_consolidated_clients()
    
    if not search_query:
        clients_data = all_clients
    else:
        clients_data = {}
        for mac, data in all_clients.items():
            # Check against all relevant fields
            in_mac = search_query in mac.lower()
            in_hostname = search_query in data.get('hostname', '').lower()
            in_ipv4 = any(search_query in ip for ip in data.get('ipv4_list', []))
            in_ipv6 = any(search_query in ip for ip in data.get('ipv6_list', []))
            
            if in_mac or in_hostname or in_ipv4 or in_ipv6:
                clients_data[mac] = data
                
    return render_template('index.html', clients=clients_data, search_query=search_query)

if __name__ == '__main__':
    # Running on 0.0.0.0 makes it accessible from your network IPs.
    # Port 8080 is used to avoid conflict with Nginx on port 80.
    print("Starting DHCP Viewer web server...")
    print("Access it via http://<your_ip_address>:8080/")
    try:
        app.run(host='0.0.0.0', port=8080, debug=False)
    except PermissionError:
        print("\n[ERROR] Permission denied to bind to port 8080.")
        print("Please run this script with 'sudo' if you choose a port < 1024.")
