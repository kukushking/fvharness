"""CertoraVerifier — wraps `certoraRun` and parses per-rule verdicts.

This is the analog of `../theorem`'s `verifier.py`: it turns a spec + contract into a
mechanical pass/fail signal. The difference: the Certora Prover runs in the *cloud*, so each
call costs seconds–minutes and Prover credits (the loop is built to minimize calls), whereas
the Lean kernel was local and ~free.

CALIBRATED 2026-06-07 against certora-cli 8.13.1 (BallGame example):
  - VERIFIED → exit 0, line "No errors found by Prover!" (no per-rule lines)
  - VIOLATED → exit 1, "ERROR: Prover found violations:" / "Violations were found", with
    per-rule "[rule] <name>:" lines.
`ok` is decided from those summary lines first, then the return code. Re-run any contest with
`--calibrate` if a future CLI version changes the wording.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RuleStatus(str, Enum):
    VERIFIED = "VERIFIED"   # property held
    VIOLATED = "VIOLATED"   # counterexample found — for a mutant, this is a CATCH
    ERROR = "ERROR"         # spec didn't compile / Prover error
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass
class VerificationResult:
    ok: bool                                # True iff no rule VIOLATED/ERROR/TIMEOUT
    rules: dict[str, RuleStatus]            # rule name -> status (best-effort; may be empty)
    returncode: int
    raw: str                                # combined stdout+stderr (for feedback + calibration)
    report_url: str | None = None           # prover.certora.com job link, if printed

    def violated(self) -> list[str]:
        return [r for r, s in self.rules.items() if s is RuleStatus.VIOLATED]

    def errored(self) -> list[str]:
        return [r for r, s in self.rules.items()
                if s in (RuleStatus.ERROR, RuleStatus.TIMEOUT)]

    def short(self) -> str:
        if self.rules:
            return ", ".join(f"{r}={s.value}" for r, s in self.rules.items())
        return f"ok={self.ok} (returncode={self.returncode}, no per-rule data parsed)"


# --- calibrated against real certoraRun output (BallGame example, certora-cli 8.13.1) ----
# VERIFIED case (exit 0): "No errors found by Prover!"
# VIOLATED case (exit 1): "ERROR: Prover found violations:" / "Violations were found", with
#   per-rule lines "[rule] <name>:" followed by "    [func] <method>()".
_SUCCESS_RE = re.compile(r"No errors found by Prover!")
_VIOLATION_RE = re.compile(r"Prover found violations|Violations were found", re.IGNORECASE)
# Violated rules are the ones the CLI lists under "found violations". Verified rules are not
# enumerated in the VERIFIED summary — so an empty rules dict + ok=True means "all held".
_RULE_RE = re.compile(r"^\s*\[rule\]\s+(?P<name>[A-Za-z_]\w*)\s*:", re.MULTILINE)
# Prefer the shareable "report url:" (carries ?anonymousKey=) over the bare job link.
_REPORT_URL_RE = re.compile(r"report url:\s*(https://prover\.certora\.com/\S+)", re.IGNORECASE)
_URL_RE = re.compile(r"https://prover\.certora\.com/output/\S+")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# certoraRun streams a "processing |/-\" spinner — collapse it so feedback stays small.
_SPINNER_RE = re.compile(r"(?:processing\s*[|/\-\\]\s*)+")


def _clean(raw: str) -> str:
    return _SPINNER_RE.sub("", _ANSI_RE.sub("", raw))


# Common brew/system locations for a real JDK, beyond whatever's on PATH.
_JAVA_CANDIDATES = [
    "java",
    "/opt/homebrew/opt/openjdk@21/bin/java",
    "/opt/homebrew/opt/openjdk/bin/java",
    "/usr/local/opt/openjdk@21/bin/java",
    "/Library/Java/JavaVirtualMachines",  # handled specially below
]


def _find_real_java() -> str | None:
    """Return the bin dir of a WORKING JDK, or None.

    macOS ships a stub `/usr/bin/java` that satisfies `which java` but isn't a real
    runtime — it returns nonzero on `-version`. So we don't trust `which`; we actually run
    `java -version` on each candidate and keep the first that succeeds.
    """
    import subprocess as _sp
    from pathlib import Path as _P
    for cand in _JAVA_CANDIDATES:
        exe = cand
        if cand.endswith("JavaVirtualMachines"):
            homes = sorted(_P(cand).glob("*/Contents/Home/bin/java")) if _P(cand).exists() else []
            exe = str(homes[-1]) if homes else None
        if not exe:
            continue
        try:
            r = _sp.run([exe, "-version"], capture_output=True, timeout=15)
            if r.returncode == 0:
                return str(_P(exe).parent)
        except (OSError, _sp.SubprocessError):
            continue
    return None


class CertoraVerifier:
    """Run `certoraRun` against a .conf and parse the outcome.

    Args:
        contest_dir: the cloned contest root (where the .conf paths are relative to).
        timeout_s:   wall-clock cap per Prover job.
        calibrate:   if True, every call prints the raw certoraRun output so you can
                     calibrate `_parse_rules` against the real format on run 1.
    """

    def __init__(self, contest_dir: Path, timeout_s: float = 1800.0,
                 calibrate: bool = False, disable_local_typecheck: bool | None = None) -> None:
        self.contest_dir = Path(contest_dir).resolve()
        self.timeout_s = timeout_s
        self.calibrate = calibrate
        # Local CVL typechecking needs a real JDK and catches malformed CVL *before* the cloud
        # round-trip — a big cheap-iteration win. Find a working JDK (not the macOS stub);
        # if found, enable local typecheck and inject its bin dir into certoraRun's PATH so
        # it works regardless of the shell's PATH. Otherwise pass --disable_local_typechecking.
        self._java_dir = _find_real_java()
        if disable_local_typecheck is None:
            disable_local_typecheck = self._java_dir is None
        self.disable_local_typecheck = disable_local_typecheck

    def _subprocess_env(self) -> dict | None:
        """certoraRun's env, with a real JDK prepended to PATH if we found one off-PATH."""
        if self._java_dir is None:
            return None
        env = dict(os.environ)
        env["PATH"] = self._java_dir + os.pathsep + env.get("PATH", "")
        return env

    @staticmethod
    def available() -> tuple[bool, str]:
        """Check that certoraRun is installed and a Prover key is set."""
        from shutil import which
        if which("certoraRun") is None:
            return False, "certoraRun not found — `pip install certora-cli`"
        if not os.environ.get("CERTORAKEY"):
            return False, "CERTORAKEY not set — get a Prover key from your contest enrollment"
        return True, "ok"

    def verify(self, conf: str | Path, cwd: Path | None = None,
               extra_args: list[str] | None = None) -> VerificationResult:
        """Run `certoraRun <conf> --wait_for_results ALL` and parse the result.

        `cwd` overrides the working directory (used by the mutation harness to run against a
        patched copy of the contest in a temp dir). `conf` is relative to that cwd.
        """
        workdir = Path(cwd) if cwd else self.contest_dir
        cmd = ["certoraRun", str(conf), "--wait_for_results", "ALL"]
        if self.disable_local_typecheck:
            cmd.append("--disable_local_typechecking")
        if extra_args:
            cmd += extra_args

        try:
            proc = subprocess.run(
                cmd, cwd=workdir, capture_output=True, text=True, timeout=self.timeout_s,
                env=self._subprocess_env(),
            )
            returncode = proc.returncode
            raw = _clean((proc.stdout or "") + "\n" + (proc.stderr or ""))
        except subprocess.TimeoutExpired as e:
            raw = _clean((e.stdout or "") + (e.stderr or ""))
            return VerificationResult(ok=False, rules={}, returncode=124,
                                      raw=raw + "\n[harness: certoraRun timed out]")

        if self.calibrate:
            print("=" * 70 + "\n[CALIBRATE] cleaned certoraRun output:\n" + raw + "\n" + "=" * 70)

        rules = self._parse_rules(raw)
        url_m = _REPORT_URL_RE.search(raw) or _URL_RE.search(raw)
        # Decide ok from the explicit summary lines first (most reliable), then the return
        # code (--wait_for_results ALL: 0=verified, nonzero=violations — confirmed on run 1).
        if _VIOLATION_RE.search(raw):
            ok = False
        elif _SUCCESS_RE.search(raw):
            ok = True
        else:
            ok = returncode == 0
        return VerificationResult(ok=ok, rules=rules, returncode=returncode, raw=raw,
                                  report_url=url_m.group(1) if (url_m and url_m.lastindex)
                                  else (url_m.group(0) if url_m else None))

    @staticmethod
    def _parse_rules(raw: str) -> dict[str, RuleStatus]:
        """Extract violated rules from the CLI's "[rule] <name>:" lines.

        Only violated rules are enumerated by certoraRun; a VERIFIED run prints just the
        "No errors" summary. So an empty dict with ok=True means every rule held — the
        mutation harness relies on this (it falls back to overall `ok` when rules is empty).
        """
        return {m.group("name"): RuleStatus.VIOLATED for m in _RULE_RE.finditer(raw)}
