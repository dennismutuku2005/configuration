<p align="center">
  <img src="https://1000logos.net/wp-content/uploads/2018/08/Huawei-Logo.png" width="300" alt="Huawei Logo">
</p>

# Huawei Router Configurator

1. A Python-based automation tool for configuring Huawei routers via Telnet protocol.
2. Supports interactive selection for multiple hardware versions including Version 5 and Version 6.
3. Automates SSID security settings and WLAN parameters through a simplified command interface.
4. Requires only standard Python libraries and network access to the router's management IP.
5. Streamlines bulk configuration tasks with a fast, headless terminal-based execution flow.

## Features

- **Bulk Index Configuration**: Automatically configures indexes from 1 to 12,345,678
- **Multi-Version Support**: Works with Huawei Version 5 and Version 6 routers
- **Automated Login**: Handles username/password authentication
- **Command Execution**: Sends configuration commands automatically
- **Progress Tracking**: Shows real-time progress during long operations
- **Custom Range Support**: Configure specific index ranges as needed

## Requirements

- Python 3.6+
- Network access to Huawei router (Telnet port 23)
- Standard Python libraries (socket, time, sys)

## Installation

```bash
# Clone or download the script
# No additional packages needed - uses only Python standard library

# Make the script executable (Linux/Mac)
chmod +x huawei_configurator.py

# Run the script
python3 huawei_configurator.py