def moving_average(values, window):
    """Average of every `window` consecutive values."""
    averages = []
    # expect: bug
    for start in range(len(values) - window):
        chunk = values[start:start + window]
        averages.append(sum(chunk) / window)
    return averages
