# Kokonut Router Tool - Real-Time PHP Backend & M-Pesa STK API

A clean, modular PHP API backend with MySQL database integration, anti-cloning hardware security, real-time token deduction lifecycle (with 5-minute safety timeout), and direct M-Pesa STK Push payment support (Till: `3018584`).

## Directory Structure

```
php_api/
├── config/
│   ├── config.php        # Global settings, constants, Till number (3018584), JSON helpers
│   └── db.php            # Pure MySQL PDO connection handler (UTF-8, prepared statements)
├── database/
│   └── schema.sql        # MySQL relational schema (devices, transactions, unlock_sessions)
├── device.php            # Real-time device registration & live token balance query
├── initiate_unlock.php   # Atomic token reservation & 5-minute session initialization
├── confirm_unlock.php    # Finalize token deduction or refund on pre-execution failure
├── mpesa_stk.php         # M-Pesa STK Push payment initiator (Till: 3018584)
├── mpesa_status.php      # Transaction status poller & real-time token crediting
└── README.md             # Documentation and deployment instructions
```

---

## Database Setup

1. Open **phpMyAdmin** or your MySQL command line.
2. Import the schema file located at `database/schema.sql`:
   ```sql
   SOURCE php_api/database/schema.sql;
   ```

---

## Configuration

Edit `config/config.php` with your live MySQL database credentials:

```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'kokonut_db');
define('DB_USER', 'your_db_username');
define('DB_PASS', 'your_db_password');
define('DB_PORT', 3306);
```

---

## API Endpoints Overview

| Endpoint | Method | Parameters | Purpose |
|---|---|---|---|
| `device.php` | POST/GET | `machine_id`, `system_info` | Verify device & fetch live token balance |
| `initiate_unlock.php` | POST | `machine_id`, `version` | Reserve tokens & start 5-min session |
| `confirm_unlock.php` | POST | `session_id`, `machine_id`, `success`, `ssids_done` | Commit deduction or refund if failed |
| `mpesa_stk.php` | POST | `phone`, `amount`, `machine_id`, `name` | Send M-Pesa STK Push to Till 3018584 |
| `mpesa_status.php` | POST | `CheckoutRequestID` | Check status & credit tokens on success |

---

## Client Application Configuration

In `application/application.py`, set:
```python
API_BASE_URL = "https://yourdomain.com/php_api"  # URL where php_api is uploaded
```
