#!/bin/bash
# PXE 監控與測試腳本

# ==============================================================================
#  功能 1: 執行一次性的 PXE 環境自我測試
#  用法: ./pxe-monitor.sh test
# ==============================================================================
run_tests() {
    echo "Running PXE self-test..."
    echo ""

    # === TFTP IPv4 測試 ===
    echo "=== 1. TFTP IPv4 Self-Test (Server: 192.168.1.1) ==="
    TMP_FILE=$(mktemp)
    
    echo -n "  - Legacy/pxelinux.0 ... "
    if tftp 192.168.1.1 -c get Legacy/pxelinux.0 "$TMP_FILE" >/dev/null 2>&1; then echo "OK"; else echo "FAILED"; fi
    
    echo -n "  - UEFI/grubx64.efi ... "
    if tftp 192.168.1.1 -c get UEFI/grubx64.efi "$TMP_FILE" >/dev/null 2>&1; then echo "OK"; else echo "FAILED"; fi
    
    echo ""
    # === TFTP IPv6 測試 ===
    echo "=== 2. TFTP IPv6 Self-Test (Server: fd00:192:168:1::1) ==="
    echo -n "  - UEFI/bootx64.efi ... "
    if tftp fd00:192:168:1::1 -c get UEFI/bootx64.efi "$TMP_FILE" >/dev/null 2>&1; then echo "OK"; else echo "FAILED"; fi

    rm -f "$TMP_FILE"
    echo ""

    # === HTTP iPXE 測試 ===
    echo "=== 3. HTTP iPXE Self-Test (Server: 192.168.1.1) ==="
    echo -n "  - http://192.168.1.1/boot.ipxe ... "
    if curl -s --head http://192.168.1.1/boot.ipxe | grep -q "200 OK"; then
        echo "OK"
    else
        if ! curl -sI http://192.168.1.1/boot.ipxe > /dev/null; then
            echo "FAILED (Cannot connect to HTTP server)"
        else
            STATUS=$(curl -sI http://192.168.1.1/boot.ipxe | head -n 1)
            echo "FAILED (Server responded with: ${STATUS:-'Unknown Error'})"
        fi
    fi
    exit 0
}

# ==============================================================================
#  功能 2: 持續監控服務日誌 (預設行為)
#  用法: ./pxe-monitor.sh
# ==============================================================================
monitor_logs() {
    echo "Starting continuous log monitoring... (Press Ctrl+C to stop)"
    echo ""
    
    echo "=== DHCP 日誌 ==="
    journalctl -u isc-dhcp-server -f | grep --line-buffered "DHCP" &
    
    echo "=== TFTP 日誌 ==="
    tail -f /var/log/syslog | grep --line-buffered "in.tftpd" &
    
    echo "=== Nginx 存取日誌 ==="
    tail -f /var/log/nginx/access.log &
    
    # 等待所有背景程序
    wait
}

# ==============================================================================
#  主程式邏輯: 根據參數決定要執行哪個功能
# ==============================================================================
if [[ "$1" == "test" || "$1" == "check" ]]; then
    run_tests
else
    monitor_logs
fi
