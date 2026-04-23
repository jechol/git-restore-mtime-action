import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "git-restore-mtime"


class GitRestoreMtimeRenameTests(unittest.TestCase):
    maxDiff = None

    def make_repo(self):
        tmpdir = tempfile.TemporaryDirectory()
        repo = pathlib.Path(tmpdir.name)
        self.addCleanup(tmpdir.cleanup)
        self.git(repo, "init", "-q")
        self.git(repo, "config", "user.name", "Test User")
        self.git(repo, "config", "user.email", "test@example.com")
        return repo

    def git(self, repo, *args, env=None):
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        subprocess.run(
            ["git", *args],
            cwd=repo,
            env=proc_env,
            check=True,
            text=True,
            capture_output=True,
        )

    def commit_all(self, repo, message, when):
        env = {
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
        }
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", message, env=env)

    def run_restore(self, repo, *args):
        subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=repo,
            check=True,
            text=True,
            capture_output=True,
        )

    def test_pure_rename_keeps_original_file_timestamp(self):
        repo = self.make_repo()
        oldfile = repo / "docs" / "old-name.txt"
        newfile = repo / "docs" / "new-name.txt"

        oldfile.parent.mkdir(parents=True)
        oldfile.write_text("hello\n", encoding="utf-8")
        self.commit_all(repo, "initial", "2020-01-01T00:00:00Z")

        self.git(repo, "mv", str(oldfile.relative_to(repo)), str(newfile.relative_to(repo)))
        self.commit_all(repo, "rename", "2021-01-01T00:00:00Z")

        os.utime(newfile, (1760000000, 1760000000))
        self.run_restore(repo)

        self.assertEqual(newfile.stat().st_size, len("hello\n"))
        self.assertEqual(int(newfile.stat().st_mtime), 1577836800)

    def test_rename_with_content_change_uses_rename_commit_timestamp(self):
        repo = self.make_repo()
        oldfile = repo / "notes.txt"
        newfile = repo / "archive" / "notes-renamed.txt"

        oldfile.write_text("hello\n", encoding="utf-8")
        self.commit_all(repo, "initial", "2020-01-01T00:00:00Z")

        newfile.parent.mkdir(parents=True)
        self.git(repo, "mv", str(oldfile.relative_to(repo)), str(newfile.relative_to(repo)))
        with newfile.open("a", encoding="utf-8") as handle:
            handle.write("updated\n")
        self.commit_all(repo, "rename and edit", "2021-01-01T00:00:00Z")

        os.utime(newfile, (1760000000, 1760000000))
        self.run_restore(repo)

        self.assertEqual(newfile.read_text(encoding="utf-8"), "hello\nupdated\n")
        self.assertEqual(int(newfile.stat().st_mtime), 1609459200)

    def test_single_pathspec_follows_rename_history(self):
        repo = self.make_repo()
        oldfile = repo / "src" / "before.txt"
        newfile = repo / "src" / "after.txt"

        oldfile.parent.mkdir(parents=True)
        oldfile.write_text("content\n", encoding="utf-8")
        self.commit_all(repo, "initial", "2020-01-01T00:00:00Z")

        self.git(repo, "mv", str(oldfile.relative_to(repo)), str(newfile.relative_to(repo)))
        self.commit_all(repo, "rename", "2021-01-01T00:00:00Z")

        os.utime(newfile, (1760000000, 1760000000))
        self.run_restore(repo, str(newfile.relative_to(repo)))

        self.assertEqual(int(newfile.stat().st_mtime), 1577836800)


if __name__ == "__main__":
    unittest.main()
