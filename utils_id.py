import os

def get_next_answer_id():
    path = "data/last_id.txt"
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("1")
            return "1"
    with open(path, "r") as f:
        last_id = int(f.read())
    new_id = str(last_id + 1)
    with open(path, "w") as f:
        f.write(new_id)
    return new_id
