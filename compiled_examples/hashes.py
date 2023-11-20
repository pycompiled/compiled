"""Finds similar SHA1's in the poetry.lock file."""
import sys
import compiled.difflib as difflib
import compiled.tomllib as tomllib

filepath = sys.argv[1]
with open(filepath, "rb") as file:
    contents = tomllib.load(file)

hashes = {
    file["hash"] for package in contents["package"] for file in package["files"][:10]
}
for hash in hashes:
    matches = difflib.get_close_matches(hash, hashes - {hash}, n=1, cutoff=0.9)
    if not matches:
        continue

    match = matches[0]
    print("Similar hashes:", hash, match)
