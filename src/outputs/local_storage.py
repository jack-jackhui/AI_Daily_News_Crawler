# outputs/local_storage.py
def save_summary_to_file(summary: str, filename="latest_summary.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
