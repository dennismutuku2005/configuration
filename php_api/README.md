# Kokonut Router Tool - Real-Time PHP Backend & M-Pesa STK API

A clean, modular PHP API backend with MySQL database integration, anti-cloning hardware security, real-time token deduction lifecycle (with 5-minute safety timeout), direct M-Pesa STK Push payment support (Till: `3018584`), and **Remote Application Version Control & Usage Blocking**.

## Live Production URL

**Base URL**: `https://kokonut.onenetwork-system.com`

---

## Token Pricing & Unlock Economics

- **1 Token = KES 1.00**
- **HG8145V5 Router Unlock**: `50 tokens` (KES 50)
- **HG8145V6 Router Unlock**: `70 tokens` (KES 70)
- **M-Pesa Payment Till Number**: `3018584`

---

## Directory Structure

```
php_api/
├── config/
│   ├── config.php        # Global settings, constants (V5=50, V6=70), Till number (3018584), JSON helpers
│   └── db.php            # Pure MySQL PDO connection handler (UTF-8, prepared statements)
├── database/
│   └── schema.sql        # MySQL relational schema (devices, app_versions, transactions, unlock_sessions)
├── check_version.php     # Remote version checking & distribution blocking endpoint
├── device.php            # Real-time device registration & live token balance query
├── initiate_unlock.php   # Atomic token reservation & 5-minute session initialization
├── confirm_unlock.php    # Finalize token deduction or refund on pre-execution failure
├── mpesa_stk.php         # M-Pesa STK Push payment initiator (Till: 3018584)
├── mpesa_status.php      # Transaction status poller & real-time token crediting
└── README.md             # Documentation and deployment instructions
```

---

## Remote App Version Control & Blocking

The `app_versions` table allows you to control which desktop application versions are allowed to run and block outdated versions remotely.

### Setting Minimum Allowed Version / Blocking Outdated Releases

In your MySQL database:

```sql
-- Require all users to update to at least version 2.1.0
UPDATE `app_versions` 
SET `min_version` = '2.1.0', 
    `latest_version` = '2.1.0', 
    `download_url` = 'https://kokonut.onenetwork-system.com/download', 
    `update_message` = 'Version 2.0.0 is deprecated. Please download Kokonut v2.1.0 to continue.',
    `is_force_update` = 1
WHERE `id` = 1;

-- Explicitly block a specific rogue or compromised version (e.g. 1.0.0, 1.9.5)
UPDATE `app_versions` 
SET `blocked_versions` = '1.0.0,1.9.5'
WHERE `id` = 1;
```

---

## Database Setup

1. Open **phpMyAdmin** or MySQL CLI on `kokonut.onenetwork-system.com`.
2. Import the schema file located at `database/schema.sql`:
   ```sql
   SOURCE php_api/database/schema.sql;
   ```

---

## Configuration

Edit `config/config.php` with your live MySQL database credentials:

```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'your_db_name');
define('DB_USER', 'your_db_username');
define('DB_PASS', 'your_db_password');
define('DB_PORT', 3306);
```

---

## API Endpoints Overview

| Endpoint | Method | Parameters | Purpose |
|---|---|---|---|
| `check_version.php` | POST/GET | `app_version`, `machine_id` | Check version validity, block outdated versions, get update URL |
| `device.php` | POST/GET | `machine_id`, `app_version`, `system_info` | Verify device, track app version, & fetch live token balance |
| `initiate_unlock.php` | POST | `machine_id`, `version`, `app_version` | Server-side version check, reserve tokens (V5: 50, V6: 70), & start 5-min session |
| `confirm_unlock.php` | POST | `session_id`, `machine_id`, `success`, `ssids_done` | Commit deduction or refund if failed |
| `mpesa_stk.php` | POST | `phone`, `amount`, `machine_id`, `name` | Send M-Pesa STK Push to Till 3018584 |
| `mpesa_status.php` | POST | `CheckoutRequestID` | Check status & credit tokens on success |
