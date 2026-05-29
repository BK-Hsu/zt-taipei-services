#!/usr/bin/env python3
import subprocess
import re
import sys
import os

def get_default_gateway_and_interface():
    """Detects the default interface and its subnet."""
    try:
        # Get default route
        route_output = subprocess.check_output(["ip", "route", "show", "default"]).decode()
        match = re.search(r"dev (\S+)", route_output)
        if not match:
            return None, None
        
        interface = match.group(1)
        
        # Get interface address/subnet
        addr_output = subprocess.check_output(["ip", "-4", "addr", "show", interface]).decode()
        match = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", addr_output)
        if not match:
            return interface, None
            
        return interface, match.group(1)
    except Exception as e:
        print(f"Error detecting network: {e}")
        return None, None

def run_arp_scan(target, silent=False):
    """Runs nmap ARP scan and parses the result."""
    if not silent:
        print(f"Scanning {target} using nmap (ARP scan)...")
    try:
        # -sn: Ping Scan - disable port scan
        # -PR: ARP Ping
        # -n: Never do DNS resolution
        cmd = ["sudo", "nmap", "-sn", "-PR", "-n", target]
        
        # Check if we can run sudo without password or if we are root
        if os.geteuid() != 0:
            print("Warning: ARP scan usually requires root privileges. Attempting with sudo...")
            
        output = subprocess.check_output(cmd).decode()
        return output
    except subprocess.CalledProcessError as e:
        print(f"Error running nmap: {e}")
        return None

def parse_nmap_output(output):
    """Parses nmap output to find IP and MAC addresses."""
    results = []
    # Match blocks of:
    # Nmap scan report for 192.168.1.1
    # Host is up (0.00052s latency).
    # MAC Address: 00:11:22:33:44:55 (Vendor)
    
    current_ip = None
    for line in output.splitlines():
        ip_match = re.search(r"Nmap scan report for (\d+\.\d+\.\d+\.\d+)", line)
        if ip_match:
            current_ip = ip_match.group(1)
            continue
            
        mac_match = re.search(r"MAC Address: ([0-9A-Fa-f:]+) \((.*)\)", line)
        if mac_match and current_ip:
            results.append({
                "ip": current_ip,
                "mac": mac_match.group(1),
                "vendor": mac_match.group(2)
            })
            current_ip = None
        elif "Host is up" in line and current_ip and "MAC Address" not in output:
             # This might happen for the local host itself (nmap doesn't show MAC for local interface)
             pass

    return results

import argparse
import json

def main():
    parser = argparse.ArgumentParser(description="ARP Scanner")
    parser.add_argument("target", nargs="?", help="Target subnet (e.g., 192.168.1.0/24)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    if args.target:
        target = args.target
    else:
        interface, subnet = get_default_gateway_and_interface()
        if not subnet:
            if args.json:
                print(json.dumps({"error": "Could not auto-detect subnet"}))
            else:
                print("Could not auto-detect subnet. Please provide a target (e.g., 192.168.1.0/24)")
            sys.exit(1)
        target = subnet
        if not args.json:
            print(f"Auto-detected subnet: {target} on interface {interface}")

    output = run_arp_scan(target, silent=args.json)
    if not output:
        if args.json:
            print(json.dumps({"error": "Scan failed"}))
        sys.exit(1)

    devices = parse_nmap_output(output)
    
    if args.json:
        print(json.dumps(devices))
    else:
        print("\nARP Scan Results:")
        print("-" * 60)
        print(f"{'IP Address':<15} {'MAC Address':<20} {'Vendor'}")
        print("-" * 60)
        
        for dev in devices:
            print(f"{dev['ip']:<15} {dev['mac']:<20} {dev['vendor']}")
        
        print("-" * 60)
        print(f"Found {len(devices)} active devices.")

if __name__ == "__main__":
    main()
