<?php
/**
 * Confirm / Finalize Router Unlock Session
 * Endpoint: POST confirm_unlock.php
 * Payload: { "session_id": "...", "machine_id": "...", "success": true|false, "ssids_done": [...] }
 */

require_once __DIR__ . '/config/db.php';

$input = getJsonInput();
$session_id = trim($input['session_id'] ?? '');
$machine_id = trim($input['machine_id'] ?? '');
$success = !empty($input['success']);
$ssids_done = $input['ssids_done'] ?? [];
$ssids_str = is_array($ssids_done) ? implode(',', $ssids_done) : (string)$ssids_done;

if (empty($session_id) || empty($machine_id)) {
    jsonResponse('error', 'Session ID and Machine ID are required.', null, 400);
}

$pdo = getDBConnection();

$stmt = $pdo->prepare("SELECT * FROM unlock_sessions WHERE session_id = ? AND machine_id = ?");
$stmt->execute([$session_id, $machine_id]);
$session = $stmt->fetch();

if (!$session) {
    jsonResponse('error', 'Invalid or expired session.', null, 404);
}

if ($session['status'] !== 'initiated') {
    jsonResponse('success', "Session already finalized as '{$session['status']}'.", [
        'session_id' => $session_id,
        'status' => $session['status']
    ]);
}

$cost = (int)$session['cost_tokens'];

if ($success || !empty($ssids_done)) {
    // Operation was successful or at least one SSID was modified -> Finalize completion
    $upd = $pdo->prepare("UPDATE unlock_sessions SET status = 'completed', ssids_done = ? WHERE session_id = ?");
    $upd->execute([$ssids_str, $session_id]);

    $balStmt = $pdo->prepare("SELECT token_balance FROM devices WHERE machine_id = ?");
    $balStmt->execute([$machine_id]);
    $currentBalance = (int)$balStmt->fetchColumn();

    jsonResponse('success', 'Unlock session confirmed and completed.', [
        'session_id' => $session_id,
        'status' => 'completed',
        'ssids_configured' => $ssids_str,
        'tokens_used' => $cost,
        'current_balance' => $currentBalance
    ]);
} else {
    // Total failure before any SSID was touched -> Refund tokens safely
    $pdo->beginTransaction();
    try {
        $refund = $pdo->prepare("UPDATE devices SET token_balance = token_balance + ? WHERE machine_id = ?");
        $refund->execute([$cost, $machine_id]);

        $upd = $pdo->prepare("UPDATE unlock_sessions SET status = 'refunded', ssids_done = 'none' WHERE session_id = ?");
        $upd->execute([$session_id]);

        $balStmt = $pdo->prepare("SELECT token_balance FROM devices WHERE machine_id = ?");
        $balStmt->execute([$machine_id]);
        $newBalance = (int)$balStmt->fetchColumn();

        $pdo->commit();

        jsonResponse('success', 'Unlock failed before configuration. Tokens refunded.', [
            'session_id' => $session_id,
            'status' => 'refunded',
            'tokens_refunded' => $cost,
            'current_balance' => $newBalance
        ]);
    } catch (Exception $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        jsonResponse('error', 'Refund error: ' . $e->getMessage(), null, 500);
    }
}
