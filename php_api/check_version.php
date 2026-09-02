<?php
/**
 * Remote App Version Check & Usage Blocking Endpoint
 * Endpoint: POST / GET check_version.php
 * Payload: { "app_version": "2.0.0", "machine_id": "..." }
 */

require_once __DIR__ . '/config/db.php';

$input = getJsonInput();
$clientVersion = trim($input['app_version'] ?? $_GET['app_version'] ?? '1.0.0');
$machineId = trim($input['machine_id'] ?? $_GET['machine_id'] ?? '');

$pdo = getDBConnection();

// Fetch latest version policy from database
$stmt = $pdo->query("SELECT * FROM app_versions ORDER BY id DESC LIMIT 1");
$policy = $stmt->fetch();

if (!$policy) {
    // Default fallback policy
    $policy = [
        'min_version'      => '2.0.0',
        'latest_version'   => '2.0.0',
        'download_url'     => 'https://kokonut.onenetwork-system.com/download',
        'update_message'   => 'Please update your application to continue.',
        'is_force_update'  => 1,
        'blocked_versions' => ''
    ];
}

$minVersion = $policy['min_version'];
$latestVersion = $policy['latest_version'];
$downloadUrl = $policy['download_url'];
$updateMsg = $policy['update_message'];
$isForceUpdate = (bool)$policy['is_force_update'];

// Check explicit blocked versions list (comma separated)
$blockedList = array_filter(array_map('trim', explode(',', $policy['blocked_versions'] ?? '')));

$isAllowed = true;
$isUpdateAvailable = false;
$blockReason = '';

if (in_array($clientVersion, $blockedList, true)) {
    $isAllowed = false;
    $blockReason = "This specific app version ({$clientVersion}) has been disabled by the administrator.";
} elseif (version_compare($clientVersion, $minVersion, '<')) {
    if ($isForceUpdate) {
        $isAllowed = false;
        $blockReason = "Version {$clientVersion} is outdated and no longer supported. Minimum required version is {$minVersion}.";
    } else {
        $isUpdateAvailable = true;
    }
} elseif (version_compare($clientVersion, $latestVersion, '<')) {
    $isUpdateAvailable = true;
}

// Update device record with current version if machine_id provided
if (!empty($machineId)) {
    try {
        $upd = $pdo->prepare("UPDATE devices SET app_version = ? WHERE machine_id = ?");
        $upd->execute([$clientVersion, $machineId]);
    } catch (Exception $e) {
        // Silently continue if update fails
    }
}

if (!$isAllowed) {
    jsonResponse('blocked', $blockReason, [
        'is_allowed'          => false,
        'is_update_available' => true,
        'client_version'      => $clientVersion,
        'min_version'         => $minVersion,
        'latest_version'      => $latestVersion,
        'download_url'        => $downloadUrl,
        'update_message'      => $updateMsg
    ], 403);
}

jsonResponse('success', $isUpdateAvailable ? 'An update is available.' : 'Application is up to date and active.', [
    'is_allowed'          => true,
    'is_update_available' => $isUpdateAvailable,
    'client_version'      => $clientVersion,
    'min_version'         => $minVersion,
    'latest_version'      => $latestVersion,
    'download_url'        => $downloadUrl,
    'update_message'      => $updateMsg
]);
