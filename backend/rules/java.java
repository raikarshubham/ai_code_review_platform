// Test fixture for java.yml. Never compiled or executed.
import java.io.*;
import java.security.MessageDigest;
import java.sql.*;

public class Fixture {
    // ruleid: java-hardcoded-secret
    private static final String PASSWORD = "s3cr3t!";
    // ruleid: java-hardcoded-secret
    String apiKey = "AKIA1234567890";
    // ok: java-hardcoded-secret
    String username = "admin";
    // ok: java-hardcoded-secret
    String password = System.getenv("DB_PASSWORD");

    void commands(String userInput) throws IOException {
        // ruleid: java-command-injection
        Runtime.getRuntime().exec("ping " + userInput);
        // ruleid: java-command-injection
        new ProcessBuilder("sh", "-c", "ls " + userInput);
        // ok: java-command-injection
        Runtime.getRuntime().exec(new String[] {"ping", userInput});
        // ok: java-command-injection
        Runtime.getRuntime().exec("uptime");
    }

    void queries(Connection conn, Statement stmt, String name) throws SQLException {
        // ruleid: java-sql-injection
        stmt.executeQuery("SELECT * FROM users WHERE name = '" + name + "'");
        // ruleid: java-sql-injection
        conn.prepareStatement("DELETE FROM users WHERE name = " + name);
        // ruleid: java-sql-injection
        stmt.execute(String.format("DROP TABLE %s", name));
        // ok: java-sql-injection
        PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE name = ?");
        // ok: java-sql-injection
        ps.setString(1, name);
    }

    void hashes() throws Exception {
        // ruleid: java-weak-hash
        MessageDigest.getInstance("MD5");
        // ruleid: java-weak-hash
        MessageDigest.getInstance("SHA-1");
        // ok: java-weak-hash
        MessageDigest.getInstance("SHA-256");
    }

    Object load(InputStream raw) throws Exception {
        ObjectInputStream in = new ObjectInputStream(raw);
        // ruleid: java-unsafe-deserialization
        return in.readObject();
    }

    void swallow() {
        // Semgrep reports the match at the start of the whole try statement.
        // ruleid: java-empty-catch
        try {
            risky();
        } catch (Exception e) {}

        // ok: java-empty-catch
        try {
            risky();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    boolean compare(String role) {
        // ruleid: java-string-reference-equality
        if (role == "admin") { return true; }
        // ok: java-string-reference-equality
        return "admin".equals(role);
    }

    void risky() {}

    void twoStepQueries(Statement stmt, String name) throws SQLException {
        String query = "SELECT * FROM users WHERE name = '" + name + "'";
        // ruleid: java-sql-injection
        stmt.executeQuery(query);
        String sql = String.format("DELETE FROM users WHERE name = %s", name);
        // ruleid: java-sql-injection
        stmt.executeUpdate(sql);
        String safe = "SELECT * FROM users";
        // ok: java-sql-injection
        stmt.executeQuery(safe);
    }
}
