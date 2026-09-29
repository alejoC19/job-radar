import os
from io import BytesIO
from unittest.mock import Mock, patch

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-key")

from docx import Document  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)


def fake_response(status_code=200, json_data=None):
    response = Mock()
    response.status_code = status_code
    response.json = Mock(return_value=json_data)
    response.raise_for_status = Mock()
    return response


def profiles_and_listings_side_effect(profile_rows, listing_rows):
    def _side_effect(url, **kwargs):
        if url.endswith("/rest/v1/cv_profiles"):
            return fake_response(json_data=profile_rows)
        if url.endswith("/rest/v1/job_listings"):
            return fake_response(json_data=listing_rows)
        raise AssertionError(f"unexpected GET {url}")

    return _side_effect


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_generate_requires_authorization_header():
    response = client.post("/generate")
    assert response.status_code == 401


def test_generate_returns_401_when_supabase_rejects_token():
    unauthorized = fake_response(status_code=401)
    with patch("api.main.requests.get", return_value=unauthorized):
        response = client.post("/generate", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


def test_generate_returns_400_when_no_profiles():
    with patch("api.main.requests.get", return_value=fake_response(json_data=[])):
        response = client.post("/generate", headers={"Authorization": "Bearer token"})
    assert response.status_code == 400


def test_generate_builds_and_returns_excel_from_recent_listings():
    profile_rows = [{"id": "p1", "name": "QA Automation", "keywords": {"selenium": 3, "qa": 3}}]
    listing_rows = [
        {
            "title": "QA Automation Tester Junior",
            "company": "Acme",
            "url": "https://example.com/1",
            "description": "Selenium, remoto",
            "location": "CABA",
            "salary_text": None,
            "source": "fake",
        }
    ]

    with patch(
        "api.main.requests.get",
        side_effect=profiles_and_listings_side_effect(profile_rows, listing_rows),
    ):
        response = client.post("/generate", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    workbook = load_workbook(BytesIO(response.content))
    assert "QA Automation" in workbook.sheetnames
    sheet = workbook["QA Automation"]
    assert sheet.cell(row=2, column=1).value == "QA Automation Tester Junior"


def test_profile_from_cv_requires_authorization_header():
    response = client.post("/profiles/from-cv", files={"file": ("cv.docx", b"x", "application/octet-stream")})
    assert response.status_code == 401


def test_profile_from_cv_rejects_invalid_token():
    with patch("api.main.requests.get", return_value=fake_response(status_code=401)):
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer bad-token"},
            files={"file": ("cv.docx", b"x", "application/octet-stream")},
        )
    assert response.status_code == 401


def test_profile_from_cv_rejects_unsupported_extension():
    with patch("api.main.requests.get", return_value=fake_response(status_code=200)):
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.txt", b"hola", "text/plain")},
        )
    assert response.status_code == 400


def test_profile_from_cv_extracts_profile_from_docx():
    docx_bytes = make_docx_bytes(
        [
            "Juan Perez - QA Automation Engineer",
            "Experiencia con Selenium, Playwright y Python.",
            "3 anios de experiencia en testing automatizado.",
        ]
    )
    fake_parsed = main._GeminiCvSchema(
        name="QA Automation",
        keywords=[
            {"keyword": "selenium", "weight": 3},
            {"keyword": "playwright", "weight": 3},
            {"keyword": "python", "weight": 2},
        ],
    )
    fake_response_obj = Mock(parsed=fake_parsed)

    with patch("api.main.requests.get", return_value=fake_response(status_code=200)), \
            patch("api.main.GEMINI_API_KEY", "fake-key"), \
            patch("api.main.gemini_client.models.generate_content", return_value=fake_response_obj) as mock_create:
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {"name": "QA Automation", "keywords": {"selenium": 3, "playwright": 3, "python": 2}}
    assert mock_create.call_args.kwargs["model"] == "gemini-3.1-flash-lite"


def test_profile_from_cv_returns_500_when_gemini_key_missing():
    docx_bytes = make_docx_bytes(["Juan Perez - QA Automation Engineer, Selenium y Python."])

    with patch("api.main.requests.get", return_value=fake_response(status_code=200)), \
            patch("api.main.GEMINI_API_KEY", None):
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 500


def test_profile_from_cv_returns_502_when_gemini_api_errors():
    docx_bytes = make_docx_bytes(["Juan Perez - QA Automation Engineer, Selenium y Python."])
    api_error = genai_errors.APIError(code=400, response_json={"error": {"message": "Bad request"}})

    with patch("api.main.requests.get", return_value=fake_response(status_code=200)), \
            patch("api.main.GEMINI_API_KEY", "fake-key"), \
            patch("api.main.gemini_client.models.generate_content", side_effect=api_error) as mock_create:
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 502
    assert mock_create.call_count == 1


def test_profile_from_cv_retries_on_503_then_succeeds():
    docx_bytes = make_docx_bytes(["Juan Perez - QA Automation Engineer, Selenium y Python."])
    overloaded = genai_errors.APIError(code=503, response_json={"error": {"message": "High demand"}})
    fake_parsed = main._GeminiCvSchema(
        name="QA Automation",
        keywords=[{"keyword": "selenium", "weight": 3}],
    )
    fake_response_obj = Mock(parsed=fake_parsed)

    with patch("api.main.requests.get", return_value=fake_response(status_code=200)), \
            patch("api.main.GEMINI_API_KEY", "fake-key"), \
            patch("api.main.time.sleep"), \
            patch(
                "api.main.gemini_client.models.generate_content",
                side_effect=[overloaded, fake_response_obj],
            ) as mock_create:
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 200
    assert mock_create.call_count == 2


def test_profile_from_cv_returns_502_after_exhausting_retries_on_503():
    docx_bytes = make_docx_bytes(["Juan Perez - QA Automation Engineer, Selenium y Python."])
    overloaded = genai_errors.APIError(code=503, response_json={"error": {"message": "High demand"}})

    with patch("api.main.requests.get", return_value=fake_response(status_code=200)), \
            patch("api.main.GEMINI_API_KEY", "fake-key"), \
            patch("api.main.time.sleep"), \
            patch("api.main.gemini_client.models.generate_content", side_effect=overloaded) as mock_create:
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 502
    assert mock_create.call_count == main._GEMINI_MAX_ATTEMPTS


def test_profile_from_cv_returns_502_when_ai_output_unparseable():
    docx_bytes = make_docx_bytes(["Juan Perez - QA Automation Engineer, Selenium y Python."])
    fake_response_obj = Mock(parsed=None)

    with patch("api.main.requests.get", return_value=fake_response(status_code=200)), \
            patch("api.main.GEMINI_API_KEY", "fake-key"), \
            patch("api.main.gemini_client.models.generate_content", return_value=fake_response_obj):
        response = client.post(
            "/profiles/from-cv",
            headers={"Authorization": "Bearer token"},
            files={"file": ("cv.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 502
