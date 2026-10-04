# Test fixture for ruby.yml. Never executed.
require 'digest'
require 'yaml'

# ruleid: rb-hardcoded-secret
API_KEY = "sk-live-123456"
# ok: rb-hardcoded-secret
USERNAME = "admin"

def commands(path)
  # ruleid: rb-command-injection
  system("ls #{path}")
  # ruleid: rb-command-injection
  `cat #{path}`
  # ok: rb-command-injection
  system("ls", path)
  # ok: rb-command-injection
  system("ls -la")
end

def queries(name)
  # ruleid: rb-sql-injection
  User.where("name = '#{name}'")
  # ruleid: rb-sql-injection
  ActiveRecord::Base.connection.execute("DELETE FROM users WHERE name = " + name)
  # ok: rb-sql-injection
  User.where("name = ?", name)
  # ok: rb-sql-injection
  User.where(name: name)
end

def dynamic(code)
  # ruleid: rb-eval
  eval(code)
  # ok: rb-eval
  eval("1 + 1")
end

def load(data)
  # ruleid: rb-unsafe-deserialization
  Marshal.load(data)
  # ruleid: rb-unsafe-deserialization
  YAML.load(data)
  # ok: rb-unsafe-deserialization
  YAML.safe_load(data)
end

def secrets
  # ruleid: rb-hardcoded-secret
  password = "hunter2"
  # ok: rb-hardcoded-secret
  password2 = ENV["PASSWORD"]
end

def hashes(pw)
  # ruleid: rb-weak-hash
  Digest::MD5.hexdigest(pw)
  # ok: rb-weak-hash
  Digest::SHA256.hexdigest(pw)
end

def risky
  # ruleid: rb-rescue-exception
  begin
    do_work
  rescue Exception => e
    puts e
  end

  # ok: rb-rescue-exception
  begin
    do_work
  rescue StandardError => e
    puts e
  end
end

def two_step_queries(name)
  sql = "SELECT * FROM users WHERE name = '#{name}'"
  # ruleid: rb-sql-injection
  ActiveRecord::Base.connection.execute(sql)
  del = "DELETE FROM users WHERE name = " + name
  # ruleid: rb-sql-injection
  ActiveRecord::Base.connection.execute(del)
  safe = "SELECT * FROM users"
  # ok: rb-sql-injection
  ActiveRecord::Base.connection.execute(safe)
end
