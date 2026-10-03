// Test fixture for csharp.yml. Never compiled or executed.
using System;
using System.Data.SqlClient;
using System.Diagnostics;
using System.Runtime.Serialization.Formatters.Binary;
using System.Security.Cryptography;

public class Fixture
{
    // ruleid: cs-hardcoded-secret
    private const string Password = "P@ssw0rd!";
    // ruleid: cs-hardcoded-secret
    private string apiKey = "sk-live-123";
    // ok: cs-hardcoded-secret
    private string userName = "admin";
    // ok: cs-hardcoded-secret
    private string password2 = Environment.GetEnvironmentVariable("PASSWORD");

    public void Commands(string userInput)
    {
        // ruleid: cs-command-injection
        Process.Start("cmd.exe", "/c dir " + userInput);
        // ruleid: cs-command-injection
        Process.Start("ping " + userInput);
        // ok: cs-command-injection
        Process.Start("notepad.exe");
    }

    public void Queries(SqlConnection conn, string name)
    {
        // ruleid: cs-sql-injection
        var cmd = new SqlCommand("SELECT * FROM Users WHERE Name = '" + name + "'", conn);
        // ruleid: cs-sql-injection
        cmd.CommandText = "DELETE FROM Users WHERE Name = " + name;
        // ok: cs-sql-injection
        var safe = new SqlCommand("SELECT * FROM Users WHERE Name = @name", conn);
        safe.Parameters.AddWithValue("@name", name);
    }

    public void Hashes()
    {
        // ruleid: cs-weak-hash
        var md5 = MD5.Create();
        // ruleid: cs-weak-hash
        var sha1 = SHA1.Create();
        // ok: cs-weak-hash
        var sha256 = SHA256.Create();
    }

    public object Load(System.IO.Stream s)
    {
        // ruleid: cs-binary-formatter
        var formatter = new BinaryFormatter();
        return formatter.Deserialize(s);
    }

    public void Swallow()
    {
        // ruleid: cs-empty-catch
        try { Risky(); } catch (Exception e) { }
        // ruleid: cs-empty-catch
        try { Risky(); } catch { }
        // ok: cs-empty-catch
        try { Risky(); } catch (Exception e) { Console.WriteLine(e); }
    }

    private void Risky() { }
}
