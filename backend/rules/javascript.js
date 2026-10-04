// Test fixture for javascript.yml. Never executed.
const cp = require('child_process');
const { execSync } = require('child_process');

function commands(userInput) {
  // ruleid: js-command-injection
  cp.exec('ls ' + userInput);
  // ruleid: js-command-injection
  execSync(`rm -rf ${userInput}`);
  // ruleid: js-command-injection
  require('child_process').exec(userInput);
  // ok: js-command-injection
  cp.exec('ls -la');
  // ok: js-command-injection
  cp.execFile('ls', [userInput]);
  // ok: js-command-injection
  /a+b/.exec(userInput);
}

function queries(db, pool, userDb, id) {
  // ruleid: js-sql-injection
  db.query("SELECT * FROM users WHERE id = " + id);
  // ruleid: js-sql-injection
  userDb.query("SELECT * FROM users WHERE id = " + id);
  // ruleid: js-sql-injection
  pool.query(`DELETE FROM users WHERE id = ${id}`);
  // ok: js-sql-injection
  db.query("SELECT * FROM users WHERE id = ?", [id]);
  // ok: js-sql-injection
  logger.query("label " + id);
}

function dynamic(code) {
  // ruleid: js-eval
  eval(code);
  // ruleid: js-eval
  const f = new Function('a', code);
  // ruleid: js-eval
  setTimeout("doThing()", 100);
  // ok: js-eval
  setTimeout(() => doThing(), 100);
  // ok: js-eval
  JSON.parse(code);
}

// ruleid: js-hardcoded-secret
const password = "hunter2";
// ruleid: js-hardcoded-secret
const config = { apiKey: "sk-live-123456" };
// ok: js-hardcoded-secret
const password2 = process.env.PASSWORD;
// ok: js-hardcoded-secret
const emptyPassword = "";
// ok: js-hardcoded-secret
const username = "admin";

const crypto = require('crypto');
// ruleid: js-weak-hash
crypto.createHash('md5').update('x').digest('hex');
// ruleid: js-weak-hash
crypto.createHash("sha1");
// ok: js-weak-hash
crypto.createHash('sha256');

function render(el, html) {
  // ruleid: js-xss-inner-html
  el.innerHTML = html;
  // ruleid: js-xss-inner-html
  document.write(html);
  // ok: js-xss-inner-html
  el.innerHTML = "<b>static</b>";
  // ok: js-xss-inner-html
  el.textContent = html;
}

function swallow() {
  // ruleid: js-empty-catch
  try { risky(); } catch (e) {}
  // ok: js-empty-catch
  try { risky(); } catch (e) { console.error(e); }
}

function twoStepQueries(db, pool, id) {
  const sql = "SELECT * FROM users WHERE id = " + id;
  // ruleid: js-sql-injection
  db.query(sql);
  let del = `DELETE FROM users WHERE id = ${id}`;
  // ruleid: js-sql-injection
  pool.query(del);
  const safe = "SELECT * FROM users WHERE id = ?";
  // ok: js-sql-injection
  db.query(safe, [id]);
}
