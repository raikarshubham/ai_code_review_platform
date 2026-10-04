// Test fixture for swift.yml. Never compiled or executed.
import CryptoKit
import Foundation
import WebKit

// ruleid: swift-hardcoded-secret
let apiKey = "sk-live-123456"
// ok: swift-hardcoded-secret
let userName = "admin"

func queries(db: OpaquePointer?, name: String) {
    // ruleid: swift-sql-injection
    sqlite3_exec(db, "DELETE FROM users WHERE name = '" + name + "'", nil, nil, nil)
    // ok: swift-sql-injection
    sqlite3_prepare_v2(db, "SELECT * FROM users WHERE name = ?", -1, &stmt, nil)
}

func secrets() {
    // ruleid: swift-hardcoded-secret
    var password = "hunter2"
    // ok: swift-hardcoded-secret
    let password2 = ProcessInfo.processInfo.environment["PASSWORD"]
}

func hashes(data: Data) {
    // ruleid: swift-weak-hash
    let digest = Insecure.MD5.hash(data: data)
    // ok: swift-weak-hash
    let good = SHA256.hash(data: data)
}

func web(view: WKWebView, name: String) {
    // ruleid: swift-js-injection
    view.evaluateJavaScript("greet('" + name + "')")
    // ok: swift-js-injection
    view.evaluateJavaScript("init()")
}

func urls() {
    // ruleid: swift-insecure-http-url
    let a = URL(string: "http://example.com/api")
    // ok: swift-insecure-http-url
    let b = URL(string: "https://example.com/api")
}

func load(path: String) {
    // ruleid: swift-force-try
    let text = try! String(contentsOfFile: path)
    // ok: swift-force-try
    let maybe = try? String(contentsOfFile: path)
}

func twoStepQueries(db: OpaquePointer?, name: String) {
    let sql = "DELETE FROM users WHERE name = '" + name + "'"
    // ruleid: swift-sql-injection
    sqlite3_exec(db, sql, nil, nil, nil)
    let safe = "SELECT * FROM users"
    // ok: swift-sql-injection
    sqlite3_exec(db, safe, nil, nil, nil)
}
