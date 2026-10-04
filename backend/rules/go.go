// Test fixture for go.yml. Never compiled or executed.
package fixture

import (
	"crypto/md5"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/tls"
	"database/sql"
	"fmt"
	"os"
	"os/exec"
	"strconv"
)

// ruleid: go-hardcoded-secret
const apiKey = "sk-live-abcdef"

func commands(user string) {
	// ruleid: go-command-injection
	exec.Command("sh", "-c", "ls "+user)
	// ruleid: go-command-injection
	exec.Command("bash", "-c", fmt.Sprintf("grep %s /etc/passwd", user))
	// ok: go-command-injection
	exec.Command("ls", "-la", user)
}

func queries(db *sql.DB, id string) {
	// ruleid: go-sql-injection
	db.Query(fmt.Sprintf("SELECT * FROM users WHERE id = %s", id))
	// ruleid: go-sql-injection
	db.Exec("DELETE FROM users WHERE id = " + id)
	// ok: go-sql-injection
	db.Query("SELECT * FROM users WHERE id = $1", id)
}

func secrets() {
	// ruleid: go-hardcoded-secret
	password := "hunter2"
	// ok: go-hardcoded-secret
	dbPassword := os.Getenv("DB_PASSWORD")
	// ok: go-hardcoded-secret
	username := "admin"
	fmt.Println(password, dbPassword, username)
}

func hashes(data []byte) {
	// ruleid: go-weak-hash
	md5.Sum(data)
	// ruleid: go-weak-hash
	sha1.New()
	// ok: go-weak-hash
	sha256.Sum256(data)
}

func client() *tls.Config {
	// ruleid: go-tls-insecure-skip-verify
	return &tls.Config{InsecureSkipVerify: true}
}

func safeClient() *tls.Config {
	// ok: go-tls-insecure-skip-verify
	return &tls.Config{MinVersion: tls.VersionTLS12}
}

func readAll(paths []string) {
	// ruleid: go-defer-in-loop
	for _, p := range paths {
		f, err := os.Open(p)
		if err != nil {
			continue
		}
		defer f.Close()
	}
}

func parse(s string, m map[string]int, v interface{}) {
	// ruleid: go-discarded-error
	n, _ := strconv.Atoi(s)
	// ok: go-discarded-error
	count, _ := m[s]
	// ok: go-discarded-error
	str, _ := v.(string)
	fmt.Println(n, count, str)
}

func twoStepQueries(db *sql.DB, ctx context.Context, id string) {
	query := fmt.Sprintf("SELECT * FROM users WHERE id = %s", id)
	// ruleid: go-sql-injection
	db.Query(query)
	var del string
	del = "DELETE FROM users WHERE id = " + id
	// ruleid: go-sql-injection
	db.ExecContext(ctx, del)
	safe := "SELECT * FROM users WHERE id = $1"
	// ok: go-sql-injection
	db.Query(safe, id)
}
