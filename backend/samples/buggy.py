"""Deliberately buggy sample used as a test fixture. Do NOT import or run this file.

Each problem is labelled so tests (Day 3) and prompt tuning (Day 6) can check that it is found.
"""

import hashlib
import os
import pickle
import sqlite3
import subprocess

# Hardcoded password (Bandit B105 -> high)
DB_PASSWORD = "supersecret123"


def add_item(item, items=[]):
    # Mutable default argument (Pylint W0102 -> high bug): the list is shared across calls.
    items.append(item)
    return items


def load_config(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except:  # Bare except (Pylint W0702 -> high bug): also swallows KeyboardInterrupt.
        return None


def calculate(expression):
    # eval on user input (Bandit B307 -> high)
    return eval(expression)


def cleanup(directory):
    # os.system with string concatenation (Bandit B605 -> critical): shell injection.
    os.system("rm -rf " + directory)


def run_command(user_input):
    # shell=True with user input (Bandit B602 -> critical)
    return subprocess.call(user_input, shell=True)


def find_user(username):
    conn = sqlite3.connect("users.db")
    # SQL built with string formatting (Bandit B608 -> critical): SQL injection.
    query = "SELECT * FROM users WHERE name = '%s'" % username
    return conn.execute(query).fetchall()


def hash_password(password):
    # md5 for passwords (Bandit B324 -> medium)
    return hashlib.md5(password.encode()).hexdigest()


def load_session(data):
    # Unpickling untrusted data (Bandit B301 -> high)
    return pickle.loads(data)


def process(data):
    # LOGIC BUG (Pylint misses it): if int() raises, `result` is never assigned and the
    # return line raises UnboundLocalError. The AI layer should catch this (Day 6 target).
    try:
        result = int(data) * 2
    except ValueError:
        print("invalid input")
    return result


def classify(order):
    # High cyclomatic complexity (Radon): deeply nested branching.
    if order:
        if order.get("paid"):
            if order.get("shipped"):
                if order.get("delivered"):
                    return "complete"
                elif order.get("lost"):
                    return "lost"
                else:
                    return "in transit"
            elif order.get("cancelled"):
                if order.get("refunded"):
                    return "refunded"
                else:
                    return "refund pending"
            else:
                return "awaiting shipment"
        elif order.get("expired"):
            return "expired"
        else:
            for item in order.get("items", []):
                if item.get("backorder"):
                    return "backordered"
            return "awaiting payment"
    return "empty"
