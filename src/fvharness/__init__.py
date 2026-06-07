"""fvharness — an agentic harness for Certora formal-verification contests.

LLM writes CVL specs → Certora Prover verifies → mutation testing scores coverage →
failures feed back. The Prover is the unfakeable ground truth (cf. the Lean kernel in
../theorem). See PLAYBOOK.md for the contest mechanics this is built around.
"""

from fvharness.certora import CertoraVerifier, RuleStatus, VerificationResult

__all__ = ["CertoraVerifier", "RuleStatus", "VerificationResult"]
