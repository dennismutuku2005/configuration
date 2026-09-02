<?php
/**
 * Initiate M-Pesa STK Push Payment (Fixed Till: 3018584)
 * Endpoint: POST mpesa_stk.php
 * Payload: { "phone": "07...", "amount": 100, "machine_id": "...", "name": "..." }
 */

require_once __DIR__ . '/config/db.php';

$input = getJsonInput();
$phone = trim($input['phone'] ?? '');
$amount = (int)($input['amount'] ?? 1);
$machine_id = trim($input['machine_id'] ?? '');
$name = trim($input['name'] ?? 'Kokonut Customer');

if (empty($machine_id)) {
    jsonResponse('error', 'Machine ID is required.', null, 400);
}

if (empty($phone)) {
    jsonResponse('error', 'Phone number is required.', null, 400);
}

if ($amount < 1) {
    jsonResponse('error', 'Amount must be at least KES 1.', null, 400);
}

// Format phone: strip spaces, handle +254 prefix
$phone = preg_replace('/\s+/', '', $phone);
if (strpos($phone, '+') === 0) {
    $phone = substr($phone, 1);
}

// Payload for STK Push API with fixed Till 3018584
$payload = [
    'name'        => $name,
    'phone'       => $phone,
    'amount'      => $amount,
    'paymentType' => 'till',
    'partyB'      => MPESA_TILL_NUMBER
];

// Call upstream M-Pesa STK Push API
$ch = curl_init(MPESA_STK_ENDPOINT);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Accept: application/json'
]);
curl_setopt($ch, CURLOPT_TIMEOUT, 15);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);

$response = curl_exec($ch);
$curlError = curl_error($ch);
curl_close($ch);

if ($response === false) {
    jsonResponse('error', 'Failed to connect to M-Pesa gateway: ' . $curlError, null, 502);
}

$respData = json_decode($response, true);

if (!is_array($respData) || ($respData['status'] ?? '') !== 'success') {
    $errMsg = $respData['message'] ?? 'M-Pesa payment initiation failed. Please check phone number and try again.';
    jsonResponse('error', $errMsg, $respData, 400);
}

$checkoutRequestId = $respData['data']['CheckoutRequestID'] ?? '';

if (empty($checkoutRequestId)) {
    jsonResponse('error', 'Invalid response from payment gateway (missing CheckoutRequestID).', $respData, 502);
}

// Record transaction in MySQL database
$pdo = getDBConnection();
$stmt = $pdo->prepare("
    INSERT INTO transactions (machine_id, phone, amount, tokens, checkout_request_id, status)
    VALUES (?, ?, ?, ?, ?, 'pending')
");
$stmt->execute([$machine_id, $phone, $amount, $amount, $checkoutRequestId]);

jsonResponse('success', 'STK Push sent to customer phone. Please enter your M-Pesa PIN.', [
    'CheckoutRequestID' => $checkoutRequestId,
    'phone'             => $phone,
    'amount'            => $amount,
    'tokens'            => $amount,
    'machine_id'        => $machine_id
]);
