-- =============================================================================
-- Kokonut Router Tool - Real-Time MySQL Database Schema
-- Compatible with MySQL 5.7+, MySQL 8.0+, MariaDB 10.3+
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `kokonut_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `kokonut_db`;

-- -----------------------------------------------------------------------------
-- 1. Devices Table (Machine ID as primary device key)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `devices` (
    `machine_id` VARCHAR(64) NOT NULL PRIMARY KEY,
    `token_balance` INT NOT NULL DEFAULT 0,
    `app_version` VARCHAR(20) NULL DEFAULT '2.0.0',
    `system_info` TEXT NULL,
    `is_blocked` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_balance` (`token_balance`),
    INDEX `idx_blocked` (`is_blocked`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. App Versions & Remote Distribution Control Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `app_versions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `min_version` VARCHAR(20) NOT NULL DEFAULT '2.0.0',
    `latest_version` VARCHAR(20) NOT NULL DEFAULT '2.0.0',
    `download_url` VARCHAR(255) NOT NULL DEFAULT 'https://pacewisp.co.ke/download',
    `update_message` TEXT NULL,
    `is_force_update` TINYINT(1) NOT NULL DEFAULT 1,
    `blocked_versions` TEXT NULL, -- Comma-separated list of blocked versions (e.g., '1.0.0,1.9.0')
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default app version rules if empty
INSERT INTO `app_versions` (`id`, `min_version`, `latest_version`, `download_url`, `update_message`, `is_force_update`, `blocked_versions`)
SELECT 1, '2.0.0', '2.0.0', 'https://pacewisp.co.ke/download', 'A new version of Kokonut is available. Please update to continue using the application.', 1, ''
WHERE NOT EXISTS (SELECT 1 FROM `app_versions` WHERE `id` = 1);

-- -----------------------------------------------------------------------------
-- 3. Transactions Table (M-Pesa STK Push Payments - Till 3018584)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `transactions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `machine_id` VARCHAR(64) NOT NULL,
    `phone` VARCHAR(20) NOT NULL,
    `amount` INT NOT NULL,
    `tokens` INT NOT NULL,
    `checkout_request_id` VARCHAR(100) NOT NULL UNIQUE,
    `status` ENUM('pending', 'success', 'failed') NOT NULL DEFAULT 'pending',
    `mpesa_receipt` VARCHAR(50) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_machine` (`machine_id`),
    INDEX `idx_checkout` (`checkout_request_id`),
    INDEX `idx_status` (`status`),
    CONSTRAINT `fk_tx_device` FOREIGN KEY (`machine_id`) REFERENCES `devices` (`machine_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. Unlock Sessions Table (Real-Time Token Deduction Lifecycle)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `unlock_sessions` (
    `session_id` VARCHAR(64) NOT NULL PRIMARY KEY,
    `machine_id` VARCHAR(64) NOT NULL,
    `router_version` VARCHAR(10) NOT NULL,
    `cost_tokens` INT NOT NULL,
    `status` ENUM('initiated', 'completed', 'refunded', 'timed_out') NOT NULL DEFAULT 'initiated',
    `ssids_done` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `expires_at` DATETIME NOT NULL,
    INDEX `idx_session_device` (`machine_id`),
    INDEX `idx_session_status` (`status`),
    INDEX `idx_expires` (`expires_at`),
    CONSTRAINT `fk_session_device` FOREIGN KEY (`machine_id`) REFERENCES `devices` (`machine_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
