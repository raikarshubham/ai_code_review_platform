// Starter snippet per language, each with a few deliberate problems so "Analyze" shows
// something useful on first click. Keys match the backend's language ids (GET /languages).
export const SAMPLES = {
  python: `def process(data):
    try:
        result = int(data) * 2
    except ValueError:
        print("invalid input")
    return result


def add_item(item, items=[]):
    items.append(item)
    return items
`,
  javascript: `const cp = require('child_process');

function run(userInput, db) {
  cp.exec('ls ' + userInput);
  return db.query("SELECT * FROM users WHERE id = " + userInput);
}

const password = "hunter2";
`,
  typescript: `export function compute(expr: string): number {
  return eval(expr) as number;
}

export function show(el: HTMLElement, html: string): void {
  el.innerHTML = html;
}
`,
  java: `public class UserService {
    private static final String PASSWORD = "s3cr3t!";

    boolean isAdmin(String role) {
        return role == "admin";
    }

    void find(Statement stmt, String name) throws SQLException {
        stmt.executeQuery("SELECT * FROM users WHERE name = '" + name + "'");
    }
}
`,
  csharp: `public class Reports
{
    public void Run(SqlConnection conn, string name)
    {
        var cmd = new SqlCommand("SELECT * FROM Users WHERE Name = '" + name + "'", conn);
        try { cmd.ExecuteNonQuery(); } catch (Exception e) { }
    }
}
`,
  go: `package main

import (
	"database/sql"
	"fmt"
	"os"
)

func readAll(db *sql.DB, paths []string, id string) {
	db.Query(fmt.Sprintf("SELECT * FROM users WHERE id = %s", id))
	for _, p := range paths {
		f, _ := os.Open(p)
		defer f.Close()
	}
}
`,
  rust: `use std::process::Command;

fn run(user: &str) {
    Command::new("sh").arg("-c").arg(format!("ls {}", user));
}

fn parse(s: &str) -> i32 {
    s.parse().unwrap()
}
`,
  cpp: `#include <cstdio>
#include <cstring>
#include <string>

void greet(const char *name) {
    char buf[16];
    strcpy(buf, name);
    printf(buf);
}
`,
  c: `#include <stdio.h>
#include <stdlib.h>

int main(void) {
    char name[32];
    gets(name);
    char cmd[64];
    sprintf(cmd, "echo %s", name);
    system(cmd);
    return 0;
}
`,
  php: `<?php
$password = "hunter2";

function show($conn) {
    $id = $_GET['id'];
    $result = mysqli_query($conn, "SELECT * FROM users WHERE id = " . $id);
    echo $_GET['name'];
}
`,
  ruby: `def search(name)
  User.where("name = '#{name}'")
end

def load(data)
  YAML.load(data)
end
`,
  swift: `import Foundation

let apiKey = "sk-live-123456"

func load(path: String) -> String {
    return try! String(contentsOfFile: path)
}
`,
  kotlin: `fun lengthOf(s: String?): Int {
    return s!!.length
}

fun find(db: SQLiteDatabase, id: String) {
    db.execSQL("DELETE FROM users WHERE id = $id")
}
`,
  objectivec: `@implementation Grader
- (int)grade:(int)score {
    if (score > 90) { return 1; }
    if (score > 80) { return 2; }
    if (score > 70) { return 3; }
    if (score > 60) { return 4; }
    if (score > 50) { return 5; }
    if (score > 40) { return 6; }
    if (score > 30) { return 7; }
    if (score > 20) { return 8; }
    if (score > 10) { return 9; }
    if (score > 5) { return 10; }
    return 11;
}
@end
`,
  sql: `SELECT * FROM users;

DELETE FROM orders;

UPDATE accounts SET balance = 0 WHERE id = 42;
`,
  html: `<!DOCTYPE html>
<html>
<head>
  <script src="http://cdn.example.com/lib.js"></script>
</head>
<body>
  <a href="https://example.com" target="_blank">External</a>
  <button onclick="send()">Send</button>
  <img src="/logo.png">
</body>
</html>
`,
  css: `.header {
  color: red !important;
}

.footer {}

.button {
  background blue;
}
`,
  yaml: `services:
  web:
    image: nginx:latest
    privileged: true
    environment:
      password: hunter2
`,
  json: `{
  "name": "demo-service",
  "port": 8080,
  "apiKey": "sk-live-1234567890",
  "port": 9090
}
`,
}
