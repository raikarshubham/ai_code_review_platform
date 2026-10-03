<?php
// Test fixture for php.yml. Never executed.

// ruleid: php-hardcoded-secret
$password = "hunter2";
// ruleid: php-hardcoded-secret
define("DB_PASSWORD", "s3cr3t");
// ok: php-hardcoded-secret
$username = "admin";
// ok: php-hardcoded-secret
$password2 = getenv("PASSWORD");

function commands($user) {
    // ruleid: php-command-injection
    system("ls " . $user);
    // ruleid: php-command-injection
    shell_exec($user);
    // ok: php-command-injection
    system("ls -la");
    // ok: php-command-injection
    system(escapeshellarg($user));
}

function queries($conn, $pdo, $id) {
    // ruleid: php-sql-injection
    mysqli_query($conn, "SELECT * FROM users WHERE id = " . $id);
    // ruleid: php-sql-injection
    $pdo->query("DELETE FROM users WHERE id = $id");
    // ok: php-sql-injection
    $stmt = $pdo->prepare("SELECT * FROM users WHERE id = ?");
    // ok: php-sql-injection
    $pdo->query("SELECT COUNT(*) FROM users");
}

function dynamic($code) {
    // ruleid: php-eval
    eval($code);
    // ruleid: php-eval
    $f = create_function('$a', $code);
}

function load($data) {
    // ruleid: php-unserialize
    $obj = unserialize($data);
    // ok: php-unserialize
    $safe = unserialize($data, ['allowed_classes' => false]);
}

// ruleid: php-extract-superglobal
extract($_GET);
// ok: php-extract-superglobal
$page = $_GET['page'] ?? 1;

// ruleid: php-xss-echo
echo $_GET['name'];
// ok: php-xss-echo
echo htmlspecialchars($_GET['name'], ENT_QUOTES, 'UTF-8');

function hashes($pw) {
    // ruleid: php-weak-hash
    $h = md5($pw);
    // ok: php-weak-hash
    $good = password_hash($pw, PASSWORD_DEFAULT);
}
