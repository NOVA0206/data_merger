"""Company matching engine: exact -> normalized -> fuzzy -> manual review.

Never auto-accepts an uncertain fuzzy match. If two or more master companies are
close enough to be plausible matches for one file, the file is flagged for manual
review instead of guessing.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from .models import CompanyRecord, MatchMethod, MatchRecord, MatchStatus
from .normalizer import normalize_company_name, normalized_key

FUZZY_ACCEPT_THRESHOLD = 90.0  # single best match >= this, and clear of runner-up
FUZZY_REVIEW_THRESHOLD = 78.0  # below ACCEPT but >= this -> "Possible Match"
AMBIGUITY_GAP = 4.0  # if top-2 fuzzy scores are within this gap, treat as ambiguous


class CompanyMatcher:
    def __init__(self, master_records: list[CompanyRecord]):
        self.master_records = master_records
        self._by_exact: dict[str, list[CompanyRecord]] = {}
        self._by_normalized: dict[str, list[CompanyRecord]] = {}
        for rec in master_records:
            self._by_exact.setdefault(rec.company_name.strip().upper(), []).append(rec)
            self._by_normalized.setdefault(normalized_key(rec.company_name), []).append(rec)

    def match(self, file_name: str, extracted_company_name: str, source_file_id: str) -> MatchRecord:
        exact_key = extracted_company_name.strip().upper()
        exact_hits = self._by_exact.get(exact_key, [])
        if len(exact_hits) == 1:
            m = exact_hits[0]
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=m.company_name,
                matched_row_index=m.row_index,
                status=MatchStatus.EXACT,
                method=MatchMethod.EXACT,
                confidence=1.0,
                source_file_id=source_file_id,
            )
        if len(exact_hits) > 1:
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=None,
                matched_row_index=None,
                status=MatchStatus.MANUAL_REVIEW,
                method=MatchMethod.EXACT,
                confidence=1.0,
                source_file_id=source_file_id,
                notes=f"{len(exact_hits)} master rows share the exact company name.",
            )

        norm_key = normalized_key(extracted_company_name)
        norm_hits = self._by_normalized.get(norm_key, [])
        if len(norm_hits) == 1:
            m = norm_hits[0]
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=m.company_name,
                matched_row_index=m.row_index,
                status=MatchStatus.NORMALIZED,
                method=MatchMethod.NORMALIZED,
                confidence=0.98,
                source_file_id=source_file_id,
            )
        if len(norm_hits) > 1:
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=None,
                matched_row_index=None,
                status=MatchStatus.MANUAL_REVIEW,
                method=MatchMethod.NORMALIZED,
                confidence=0.98,
                source_file_id=source_file_id,
                notes=(
                    f"{len(norm_hits)} master rows normalize to the same name: "
                    + "; ".join(h.company_name for h in norm_hits)
                ),
            )

        # Fuzzy tier
        target_norm = normalize_company_name(extracted_company_name)
        scored = []
        for rec in self.master_records:
            score = fuzz.WRatio(target_norm, normalize_company_name(rec.company_name))
            scored.append((score, rec))
        scored.sort(key=lambda t: t[0], reverse=True)

        if not scored:
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=None,
                matched_row_index=None,
                status=MatchStatus.NO_MATCH,
                method=MatchMethod.FUZZY,
                confidence=0.0,
                source_file_id=source_file_id,
                notes="Master sheet has no company records.",
            )

        best_score, best_rec = scored[0]
        runner_up_score = scored[1][0] if len(scored) > 1 else 0.0

        if best_score < FUZZY_REVIEW_THRESHOLD:
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=None,
                matched_row_index=None,
                status=MatchStatus.NO_MATCH,
                method=MatchMethod.FUZZY,
                confidence=round(best_score / 100, 4),
                source_file_id=source_file_id,
                notes=f"Best candidate '{best_rec.company_name}' scored only {best_score:.1f}.",
            )

        is_ambiguous = (best_score - runner_up_score) < AMBIGUITY_GAP and runner_up_score >= FUZZY_REVIEW_THRESHOLD
        if is_ambiguous:
            top_candidates = [r.company_name for s, r in scored[:3] if s >= FUZZY_REVIEW_THRESHOLD]
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=None,
                matched_row_index=None,
                status=MatchStatus.MANUAL_REVIEW,
                method=MatchMethod.FUZZY,
                confidence=round(best_score / 100, 4),
                source_file_id=source_file_id,
                notes="Ambiguous fuzzy candidates: " + "; ".join(top_candidates),
            )

        if best_score >= FUZZY_ACCEPT_THRESHOLD:
            status = MatchStatus.NORMALIZED  # treated as confident, but method stays Fuzzy
            return MatchRecord(
                file_name=file_name,
                extracted_company_name=extracted_company_name,
                matched_company=best_rec.company_name,
                matched_row_index=best_rec.row_index,
                status=MatchStatus.POSSIBLE,
                method=MatchMethod.FUZZY,
                confidence=round(best_score / 100, 4),
                source_file_id=source_file_id,
                notes="High-confidence fuzzy match; recommended for review before final acceptance.",
            )

        return MatchRecord(
            file_name=file_name,
            extracted_company_name=extracted_company_name,
            matched_company=best_rec.company_name,
            matched_row_index=best_rec.row_index,
            status=MatchStatus.MANUAL_REVIEW,
            method=MatchMethod.FUZZY,
            confidence=round(best_score / 100, 4),
            source_file_id=source_file_id,
            notes=f"Low-confidence fuzzy candidate '{best_rec.company_name}' ({best_score:.1f}).",
        )
