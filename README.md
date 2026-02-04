# PXE Server Configuration Summary

This repository documents the PXE server setup.

## Architecture Overview

The PXE environment utilizes a combination of DHCP, TFTP, and HTTP servers to provide network booting for various Linux distributions.

- **DHCP Server**: `isc-dhcp-server`
  - Provides IP addresses to clients on the `192.168.1.0/24` subnet.
  - Detects client architecture (UEFI, Legacy BIOS, iPXE) to provide the appropriate boot file.
- **TFTP Server**:
  - Serves the initial bootloaders.
  - `UEFI/grubx64.efi` for UEFI clients.
  - `Legacy/pxelinux.0` for Legacy BIOS clients.
- **HTTP Server**: `Nginx`
  - Serves larger files like the kernel, initrd, and OS filesystems.
  - Root directory for HTTP content is `/var/www/html`.
- **Bootloader**: `GRUB 2.06`
  - Presents a menu with various OS installation options.
- **Supported Operating Systems**:
  - Ubuntu (20.04, 22.04, 23.10)
  - RHEL 9.0
  - AWS Ubuntu 22.04

## Client Boot Flow

1.  Client broadcasts a DHCP request.
2.  The DHCP server assigns an IP and provides the TFTP server address (`192.168.1.1`) and a boot filename based on the client's architecture.
3.  Client downloads the bootloader (e.g., `grubx64.efi`) from the TFTP server.
4.  The bootloader executes and loads its configuration from the TFTP server.
5.  GRUB menu is displayed, listing available operating systems.
6.  User selects an OS.
7.  GRUB then loads the corresponding kernel and initrd image from the Nginx HTTP server.
8.  The operating system installer or live environment boots.
