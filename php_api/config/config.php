<?php
/**
 * Kokonut Router Tool - API Configuration
 */

// Set response headers for JSON and CORS
header('Content-Type: application/json; charset=UTF-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// -----------------------------------------------------------------------------
// Database Settings (MySQL / MariaDB)
// -----------------------------------------------------------------------------
define('DB_HOST', 'localhost');
define('DB_NAME', 'kokonut_db');
define('DB_USER', 'root');
define('DB_PASS', '');
define('DB_PORT', 3306);
define('DB_CHARSET', 'utf8mb4');

// -----------------------------------------------------------------------------
// M-Pesa STK Push API Settings
// -----------------------------------------------------------------------------
define('MPESA_STK_ENDPOINT', 'https://tuk.onenetwork-system.com/mpesa/v1/stkpush.php');
define('MPESA_STATUS_ENDPOINT', 'https://tuk.onenetwork-system.com/mpesa/v1/statuscheck.php');

// Fixed M-Pesa Till Number
define('MPESA_TILL_NUMBER', '3018584');

// -----------------------------------------------------------------------------
// Token Economics & Session Settings
// -----------------------------------------------------------------------------
define('COST_V5_UNLOCK', 70);       // 70 Tokens (KES 70) for HG8145V5
define('COST_V6_UNLOCK', 100);      // 100 Tokens (KES 100) for HG8145V6
define('UNLOCK_SESSION_TIMEOUT', 300); // 5 minutes timeout (in seconds)

// -----------------------------------------------------------------------------
// Helper Functions
// -----------------------------------------------------------------------------

/**
 * Output structured JSON response and terminate script
 */
function jsonResponse($status, $message, $data = null, $code = 200) {
    http_response_code($code);
    echo json_encode([
        'status'    => $status,
        'message'   => $message,
        'data'      => $data,
        'timestamp' => date('Y-m-d H:i:s')
    ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    exit;
}

/**
 * Retrieve and parse JSON input from request body or fallback to POST
 */
function getJsonInput() {
    $raw = file_get_contents('php://input');
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        return $_POST;
    }
    return $data;
}
