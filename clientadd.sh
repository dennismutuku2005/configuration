#!/bin/bash

CLIENT_NAME=$1
STATIC_IP=$2
WINBOX_PORT=$3
API_PORT=$4

# Validate input
if [[ -z "$CLIENT_NAME" || -z "$STATIC_IP" || -z "$WINBOX_PORT" || -z "$API_PORT" ]]; then
  echo "Usage: $0 <client_name> <static_ip> <winbox_port> <api_port>"
  exit 1
fi

# Step 1: Run OpenVPN installer script with automated input
{
  sleep 1   # Small delay to ensure the script is ready
  echo "1"  # Select "Add a new client"
  sleep 0.5
  echo "$CLIENT_NAME"  # Provide the client name
  sleep 0.5
} | sudo bash ./openvpn-install.sh

# Step 2: Assign static IP
CCD_DIR="/etc/openvpn/ccd"
sudo mkdir -p "$CCD_DIR"
echo "ifconfig-push $STATIC_IP 255.255.255.0" | sudo tee "$CCD_DIR/$CLIENT_NAME" > /dev/null

# Step 3: Map ports using iptables
sudo iptables -t nat -A PREROUTING -p tcp --dport "$WINBOX_PORT" -j DNAT --to-destination "$STATIC_IP:8291"
sudo iptables -t nat -A PREROUTING -p tcp --dport "$API_PORT" -j DNAT --to-destination "$STATIC_IP:8728"
sudo iptables -t nat -A POSTROUTING -s "$STATIC_IP" -j MASQUERADE

echo ""
echo "[✔] VPN client '$CLIENT_NAME' added successfully:"
echo "    ↪ Static VPN IP : $STATIC_IP"
echo "    ↪ Winbox Port    : $WINBOX_PORT → $STATIC_IP:8291"
echo "    ↪ API Port       : $API_PORT → $STATIC_IP:8728"