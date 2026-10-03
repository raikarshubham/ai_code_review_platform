// TypeScript fixture for javascript.yml (same rules, TS syntax). Never executed.
import { exec } from 'child_process';
import * as crypto from 'crypto';

export function run(user: string): void {
  // ruleid: js-command-injection
  exec(`git checkout ${user}`);
  // ok: js-command-injection
  exec('git status');
}

export async function find(db: Database, id: string): Promise<User[]> {
  // ruleid: js-sql-injection
  return db.query("SELECT * FROM users WHERE id = '" + id + "'");
}

export function compute(expr: string): number {
  // ruleid: js-eval
  return eval(expr) as number;
}

// ruleid: js-hardcoded-secret
const clientSecret: string = "abc123def456";

// ruleid: js-weak-hash
const digest = crypto.createHash('md5');

export function show(el: HTMLElement, html: string): void {
  // ruleid: js-xss-inner-html
  el.innerHTML = html;
}

export function quiet(): void {
  // ruleid: js-empty-catch
  try { JSON.parse('{'); } catch (err) {}
}
