<?php
/**
 * Device Registration & Real-Time Balance Query
 * Endpoint: POST / GET device.php
 * Payload: { "machine_id": "...", "system_info": {...} }
 */

require_once __DIR__ . '/config/db.php';

$input = getJsonInput();
$machine_id = trim($input['machine_id'] ?? $_GET['machine_id'] ?? '');

if (empty($machine_id)) {
    jsonResponse('error', 'Machine ID is required.', null, 400);
}

// Basic format validation for SHA-256 machine ID
if (strlen($machine_id) < 16 || !preg_match('/^[a-f0-9]+$/i', $machine_id)) {
    jsonResponse('error', 'Invalid machine ID format.', null, 400);
}

$pdo = getDBConnection();

// Check if device exists
$stmt = $pdo->prepare("SELECT machine_id, token_balance, is_blocked, created_at, updated_at FROM devices WHERE machine_id = ?");
$stmt->execute([$machine_id]);
$device = $stmt->fetch();

if (!$device) {
    // Register new device with initial 0 balance
    $sysInfo = json_encode($input['system_info'] ?? []);
    $insert = $pdo->prepare("INSERT INTO devices (machine_id, token_balance, system_info) VALUES (?, 0, ?)");
    $insert->execute([$machine_id, $sysInfo]);

    $device = [
        'machine_id' => $machine_id,
        'token_balance' => 0,
        'is_blocked' => 0,
        'created_at' => date('Y-m-d H:i:s')
    ];
}

if ($device['is_blocked']) {
    jsonResponse('error', 'This device has been blocked. Contact support for assistance.', null, 403);
}

jsonResponse('success', 'Device verified', [
    'machine_id' => $device['machine_id'],
    'token_balance' => (int)$device['token_balance'],
    'is_blocked' => (bool)$device['is_blocked'],
    'server_time' => date('Y-m-d H:i:s')
]);
