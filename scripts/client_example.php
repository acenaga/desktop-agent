<?php
/**
 * scripts/client_example.php: Ejemplo de cliente PHP (compatible con Laravel / Guzzle / cURL)
 * para consumir la API /v1 de LocalDesk.
 * 
 * Uso:
 * php scripts/client_example.php
 */

$apiBase = getenv('LOCALDESK_API_BASE') ?: 'http://127.0.0.1:8000';
$sessionToken = getenv('LOCALDESK_SESSION_TOKEN') ?: 'test-secret-token';

echo "============================================================\n";
echo " CLIENTE DE INTEGRACIÓN PHP / LARAVEL - LocalDesk API /v1\n";
echo "============================================================\n";

function requestApi(string $method, string $path, ?array $body = null, array $extraHeaders = [])
{
    global $apiBase, $sessionToken;
    $url = rtrim($apiBase, '/') . $path;

    $headers = array_merge([
        'Authorization: Bearer ' . $sessionToken,
        'Content-Type: application/json',
        'Accept: application/json',
    ], $extraHeaders);

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);

    if ($body !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
    }

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

    if (curl_errno($ch)) {
        $err = curl_error($ch);
        curl_close($ch);
        throw new Exception("Error de conexión cURL: " . $err);
    }

    curl_close($ch);
    return ['code' => $httpCode, 'data' => json_decode($response, true)];
}

try {
    // 1. Health check
    $health = requestApi('GET', '/v1/health');
    if ($health['code'] !== 200) {
        echo "[!] Error al conectar con LocalDesk (HTTP {$health['code']})\n";
        exit(1);
    }
    echo "[+] Conexión establecida exitosamente con LocalDesk API v{$health['data']['version']}\n";
    echo "    SO: {$health['data']['os_platform']} | Inferencia activa: " . ($health['data']['inference_available'] ? 'SÍ' : 'NO') . "\n";

    // 2. Obtener alcances disponibles
    $scopes = requestApi('GET', '/v1/scopes');
    $scopeId = !empty($scopes['data']) ? $scopes['data'][0]['scope_id'] : 'default_scope';

    // 3. Crear una nueva tarea con Idempotency-Key
    $idempotencyKey = 'laravel-job-' . time();
    $taskPayload = [
        'instruction' => 'Compara las propuestas de desarrollo en mi carpeta autorizada.',
        'scope_id' => $scopeId,
        'input_refs' => ['fixtures/uc01/propuesta_alfa.md', 'fixtures/uc01/propuesta_beta.docx'],
        'output_name' => 'comparacion.md',
    ];

    echo "\n[+] Creando tarea con Idempotency-Key: {$idempotencyKey}\n";
    $task = requestApi('POST', '/v1/tasks', $taskPayload, ["Idempotency-Key: {$idempotencyKey}"]);
    $taskId = $task['data']['task_id'];
    echo "[+] Tarea creada. ID: {$taskId}, Estado: {$task['data']['state']}\n";

    // 4. Consultar estado de la tarea
    $detail = requestApi('GET', "/v1/tasks/{$taskId}");
    echo "[+] Detalle de la tarea obtenido:\n";
    echo "    Instrucción: {$detail['data']['task']['instruction']}\n";
    echo "    Estado: {$detail['data']['task']['state']}\n";

    echo "\n============================================================\n";
    echo " Integración completada con éxito.\n";
    echo "============================================================\n";

} catch (Exception $e) {
    echo "[!] Excepción: " . $e->getMessage() . "\n";
    echo "Asegúrate de haber iniciado el servicio con: python -m local_agent.cli serve --token test-secret-token\n";
}
