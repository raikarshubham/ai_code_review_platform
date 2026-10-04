# expect-fp: B105
TOKEN_HEADER = "X-Auth-Token"


def find_user(users, name):
    for user in users:
        if user["name"] == name:
            return user


def greeting(users, name):
    user = find_user(users, name)
    # expect: bug
    return "Hello, " + user["display_name"]


def auth_headers(token):
    return {TOKEN_HEADER: token}
