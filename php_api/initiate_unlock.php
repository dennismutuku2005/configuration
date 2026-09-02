<?php
/**
 * Initiate Router Unlock Session & Real-Time Token Reservation
 * Endpoint: POST initiate_unlock.php
 * Payload: { "machine_id": "...", "version": "5"|"6", "app_version": "2.0.0" }
 */

require_once __DIR__ . '/config/db.php';

$input = getJsonInput();
$machine_id = trim($input['machine_id'] ?? '');
$version = trim($input['version'] ?? '5');
$app_version = trim($input['app_version'] ?? '1.0.0');

if (empty($machine_id)) {
    jsonResponse('error', 'Machine ID is required.', null, 400);
}

$pdo = getDBConnection();

// Server-side App Version Policy Enforcement
$verStmt = $pdo->query("SELECT * FROM app_versions ORDER BY id DESC LIMIT 1");
$policy = $verStmt->fetch();

if ($policy) {
    $minVersion = $policy['min_version'] ?? '2.0.0';
    $isForceUpdate = (bool)($policy['is_force_update'] ?? 1);
    $blockedList = array_filter(array_map('trim', explode(',', $policy['blocked_versions'] ?? '')));

    if (in_array($app_version, $blockedList, true)) {
        jsonResponse('blocked', "App version {$app_version} is blocked by administrator. Please update.", null, 403);
    }

    if ($isForceUpdate && version_compare($app_version, $minVersion, '<')) {
        jsonResponse('blocked', "App version {$app_version} is deprecated. Minimum required version is {$minVersion}. Please download the latest update.", [
            'download_url' => $policy['download_url'] ?? 'https://pacewisp.co.ke/download'
        ], 403);
    }
}

$cost = ($version === '6') ? COST_V6_UNLOCK : COST_V5_UNLOCK;

// Cleanup / Finalize any stale sessions older than 5 minutes for this machine
$staleCheck = $pdo->prepare("
    UPDATE unlock_sessions 
    SET status = 'completed' 
    WHERE machine_id = ? AND status = 'initiated' AND expires_at < NOW()
");
$staleCheck->execute([$machine_id]);

// Begin Atomic Transaction
$pdo->beginTransaction();

try {
    // Lock row for update
    $stmt = $pdo->prepare("SELECT token_balance, is_blocked FROM devices WHERE machine_id = ? FOR UPDATE");
    $stmt->execute([$machine_id]);
    $device = $stmt->fetch();

    if (!$device) {
        $pdo->rollBack();
        jsonResponse('error', 'Device not found. Please verify device first.', null, 404);
    }

    if ($device['is_blocked']) {
        $pdo->rollBack();
        jsonResponse('error', 'Device is blocked.', null, 403);
    }

    $currentBalance = (int)$device['token_balance'];

    if ($currentBalance < $cost) {
        $pdo->rollBack();
        jsonResponse('error', "Insufficient tokens. Required: {$cost} tokens, Current balance: {$currentBalance} tokens.", [
            'required_tokens' => $cost,
            'current_balance' => $currentBalance,
            'shortage' => $cost - $currentBalance
        ], 402);
    }

    // Deduct tokens atomically
    $newBalance = $currentBalance - $cost;
    $updateStmt = $pdo->prepare("UPDATE devices SET token_balance = ? WHERE machine_id = ?");
    $updateStmt->execute([$newBalance, $machine_id]);

    // Create session record with 5-minute timeout window
    $sessionId = 'sess_' . bin2hex(random_bytes(16));
    $expiresAt = date('Y-m-d H:i:s', time() + UNLOCK_SESSION_TIMEOUT);

    $sessionStmt = $pdo->prepare("
        INSERT INTO unlock_sessions (session_id, machine_id, router_version, cost_tokens, status, expires_at)
        VALUES (?, ?, ?, ?, 'initiated', ?)
    ");
    $sessionStmt->execute([$sessionId, $machine_id, $version, $cost, $expiresAt]);

    $pdo->commit();

    jsonResponse('success', 'Unlock session authorized. Tokens deducted.', [
        'session_id' => $sessionId,
        'cost_tokens' => $cost,
        'new_balance' => $newBalance,
        'expires_at' => $expiresAt
    ]);

} catch (Exception $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    jsonResponse('error', 'Transaction error: ' . $e->getMessage(), null, 500);
}
