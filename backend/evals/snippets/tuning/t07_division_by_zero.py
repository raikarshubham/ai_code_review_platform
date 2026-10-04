def average_score(scores=None):
    scores = scores or []
    # expect: bug
    return sum(scores) / len(scores)


def report(students):
    return {name: average_score(marks) for name, marks in students.items()}
