"""Publication TestFlight : un build précédent encore en vérification bêta ne fait pas échouer l'envoi."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import testflight_publish as tp  # noqa: E402


def fake_api(submission):
    def api(key_path, method, path, body=None):
        if path.startswith("/v1/builds?"):
            return {"data": [{"id": "b1", "attributes": {"processingState": "VALID", "usesNonExemptEncryption": False}}]}
        if path.endswith("/betaGroups"):
            return {"data": [{"id": "g1", "attributes": {"name": tp.GROUP_NAME}}]}
        if path.startswith("/v1/buildBetaDetails"):
            return {"data": [{"attributes": {"externalBuildState": "READY_FOR_BETA_SUBMISSION"}}]}
        if path == "/v1/betaAppReviewSubmissions":
            return submission
        return {}
    return api


def test_another_build_in_review_is_not_a_failure(monkeypatch):
    busy = {"error": 422, "detail": '{"errors":[{"code":"ENTITY_UNPROCESSABLE.ANOTHER_BUILD_IN_REVIEW"}]}'}
    monkeypatch.setattr(tp, "api", fake_api(busy))
    assert tp.main("app", "70", "key", "TV_OS") == 0


def test_other_submission_errors_still_fail(monkeypatch):
    monkeypatch.setattr(tp, "api", fake_api({"error": 403, "detail": "forbidden"}))
    assert tp.main("app", "70", "key", "TV_OS") == 1
