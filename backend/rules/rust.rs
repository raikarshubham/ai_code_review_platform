// Test fixture for rust.yml. Never compiled or executed.
use std::process::Command;

// ruleid: rust-hardcoded-secret
const API_KEY: &str = "sk-live-abcdef";

fn commands(user: &str) {
    // ruleid: rust-command-injection
    Command::new("sh").arg("-c").arg(format!("ls {}", user));
    // ok: rust-command-injection
    Command::new("ls").arg(user);
}

fn queries(conn: &Connection, id: &str) {
    // ruleid: rust-sql-injection
    conn.execute(&format!("DELETE FROM users WHERE id = {}", id), []);
    // ok: rust-sql-injection
    conn.execute("DELETE FROM users WHERE id = ?1", params![id]);
}

fn secrets() {
    // ruleid: rust-hardcoded-secret
    let password = "hunter2";
    // ok: rust-hardcoded-secret
    let username = "admin";
    // ok: rust-hardcoded-secret
    let password2 = std::env::var("PASSWORD");
}

fn hashes(data: &[u8]) {
    // ruleid: rust-weak-hash
    let digest = md5::compute(data);
    // ok: rust-weak-hash
    let good = Sha256::new();
}

fn client() {
    // ruleid: rust-tls-accept-invalid-certs
    let c = reqwest::Client::builder().danger_accept_invalid_certs(true).build();
}

fn parse(s: &str) -> i32 {
    // ruleid: rust-unwrap
    let n: i32 = s.parse().unwrap();
    // ok: rust-unwrap
    let m: i32 = s.parse().unwrap_or(0);
    n + m
}

fn raw(p: *const i32) -> i32 {
    // ruleid: rust-unsafe-block
    unsafe { *p }
}
