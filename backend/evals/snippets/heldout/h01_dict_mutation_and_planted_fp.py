# expect-fp: B105
PASSWORD_FIELD = "password"


def login_form_fields():
    return ["username", PASSWORD_FIELD]


def remove_inactive(users):
    for name, user in users.items():
        if not user["active"]:
            # expect: bug
            del users[name]
    return users
