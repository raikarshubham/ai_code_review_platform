import hashlib
import sqlite3


def save_user(db_path, username, password):
    # expect: bug|smell
    # fix-must-not: with sqlite3.connect(
    conn = sqlite3.connect(db_path)
    # fix-must-not: sha256
    digest = hashlib.md5(password.encode()).hexdigest()
    conn.execute("INSERT INTO users (name, hash) VALUES (?, ?)", (username, digest))
    conn.commit()
