// Test fixture for kotlin.yml. Never compiled or executed.
import java.security.MessageDigest

// ruleid: kt-hardcoded-secret
const val API_KEY = "sk-live-123456"
// ok: kt-hardcoded-secret
const val USER_NAME = "admin"

fun commands(user: String) {
    // ruleid: kt-command-injection
    Runtime.getRuntime().exec("ping " + user)
    // ruleid: kt-command-injection
    ProcessBuilder("sh", "-c", "ls ${user}")
    // ok: kt-command-injection
    ProcessBuilder("ls", "-la", user)
}

fun queries(db: SQLiteDatabase, id: String) {
    // ruleid: kt-sql-injection
    db.rawQuery("SELECT * FROM users WHERE id = " + id, null)
    // ruleid: kt-sql-injection
    db.execSQL("DELETE FROM users WHERE id = $id")
    // ok: kt-sql-injection
    db.rawQuery("SELECT * FROM users WHERE id = ?", arrayOf(id))
}

fun secrets() {
    // ruleid: kt-hardcoded-secret
    val password = "hunter2"
    // ok: kt-hardcoded-secret
    val password2 = System.getenv("PASSWORD")
}

fun hashes() {
    // ruleid: kt-weak-hash
    MessageDigest.getInstance("MD5")
    // ok: kt-weak-hash
    MessageDigest.getInstance("SHA-256")
}

fun lengthOf(s: String?): Int {
    // ruleid: kt-force-unwrap
    return s!!.length
}

fun safeLength(s: String?): Int {
    // ok: kt-force-unwrap
    return s?.length ?: 0
}

fun swallow() {
    // ruleid: kt-empty-catch
    try { risky() } catch (e: Exception) {}
    // ok: kt-empty-catch
    try { risky() } catch (e: Exception) { println(e) }
}

fun web(view: WebView) {
    // ruleid: kt-webview-js-interface
    view.addJavascriptInterface(Bridge(), "bridge")
}

fun twoStepQueries(db: SQLiteDatabase, id: String) {
    val sql = "SELECT * FROM users WHERE id = " + id
    // ruleid: kt-sql-injection
    db.rawQuery(sql, null)
    val del = "DELETE FROM users WHERE id = $id"
    // ruleid: kt-sql-injection
    db.execSQL(del)
    val safe = "SELECT * FROM users WHERE id = ?"
    // ok: kt-sql-injection
    db.rawQuery(safe, arrayOf(id))
}
