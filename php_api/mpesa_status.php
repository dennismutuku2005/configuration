<?php
/**
 * Query M-Pesa Transaction Status and Real-Time Credit Tokens
 * Endpoint: POST mpesa_status.php
 * Payload: { "CheckoutRequestID": "ws_CO_..." }
 */

require_once __DIR__ . '/config/db.php';

$input = getJsonInput();
$checkoutRequestId = trim($input['CheckoutRequestID'] ?? '');

if (empty($checkoutRequestId)) {
    jsonResponse('error', 'CheckoutRequestID is required.', null, 400);
}

$pdo = getDBConnection();

// Check existing transaction record in MySQL
$txStmt = $pdo->prepare("SELECT * FROM transactions WHERE checkout_request_id = ?");
$txStmt->execute([$checkoutRequestId]);
$tx = $txStmt->fetch();

if (!$tx) {
    jsonResponse('error', 'Transaction record not found.', null, 404);
}

// If transaction was already marked success, return the current balance
if ($tx['status'] === 'success') {
    $balStmt = $pdo->prepare("SELECT token_balance FROM devices WHERE machine_id = ?");
    $balStmt->execute([$tx['machine_id']]);
    $currentBalance = (int)$balStmt->fetchColumn();

    jsonResponse('success', 'Payment already verified and credited.', [
        'status'            => 'success',
        'CheckoutRequestID' => $checkoutRequestId,
        'tokens_added'      => (int)$tx['tokens'],
        'current_balance'   => $currentBalance
    ]);
}

// Query upstream status check endpoint
$ch = curl_init(MPESA_STATUS_ENDPOINT);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['CheckoutRequestID' => $checkoutRequestId]));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Accept: application/json'
]);
curl_setopt($ch, CURLOPT_TIMEOUT, 12);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);

$response = curl_exec($ch);
$curlError = curl_error($ch);
curl_close($ch);

if ($response === false) {
    jsonResponse('error', 'Failed to check status: ' . $curlError, null, 502);
}

$statusData = json_decode($response, true);
$gatewayStatus = strtolower($statusData['status'] ?? 'pending');

if ($gatewayStatus === 'pending') {
    jsonResponse('pending', $statusData['message'] ?? 'Transaction is pending customer PIN entry.', [
        'status'            => 'pending',
        'CheckoutRequestID' => $checkoutRequestId
    ]);
}

if ($gatewayStatus === 'success') {
    // Credit tokens atomically in MySQL
    $pdo->beginTransaction();
    try {
        $tokensToAdd = (int)$tx['tokens'];
        $machineId = $tx['machine_id'];

        // Update transaction status
        $updTx = $pdo->prepare("UPDATE transactions SET status = 'success' WHERE checkout_request_id = ?");
        $updTx->execute([$checkoutRequestId]);

        // Credit device tokens in database
        $updDev = $pdo->prepare("UPDATE devices SET token_balance = token_balance + ? WHERE machine_id = ?");
        $updDev->execute([$tokensToAdd, $machineId]);

        // Fetch updated balance
        $balStmt = $pdo->prepare("SELECT token_balance FROM devices WHERE machine_id = ?");
        $balStmt->execute([$machineId]);
        $newBalance = (int)$balStmt->fetchColumn();

        $pdo->commit();

        jsonResponse('success', 'Payment successful! Tokens added to your account.', [
            'status'            => 'success',
            'CheckoutRequestID' => $checkoutRequestId,
            'tokens_added'      => $tokensToAdd,
            'current_balance'   => $newBalance
        ]);
    } catch (Exception $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        jsonResponse('error', 'Failed to credit tokens: ' . $e->getMessage(), null, 500);
    }
}

// Payment failed
if ($gatewayStatus === 'failure' || $gatewayStatus === 'failed') {
    $updTx = $pdo->prepare("UPDATE transactions SET status = 'failed' WHERE checkout_request_id = ?");
    $updTx->execute([$checkoutRequestId]);

    jsonResponse('failure', $statusData['message'] ?? 'Payment failed or cancelled by user.', [
        'status'            => 'failure',
        'CheckoutRequestID' => $checkoutRequestId,
        'details'           => $statusData['data']['ResultDesc'] ?? 'Transaction rejected'
    ]);
}

jsonResponse('pending', 'Checking status...', $statusData);
