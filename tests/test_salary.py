from job_radar.salary import extract_salary


def test_extracts_range_with_dollar_sign():
    assert extract_salary("Se ofrece $500.000 - $700.000 mensual") == "$500.000 - $700.000"


def test_extracts_usd_amount():
    assert extract_salary("Salario USD 1500 mensuales") == "USD 1500"


def test_extracts_ars_amount():
    assert extract_salary("Sueldo ARS 800.000") == "ARS 800.000"


def test_returns_none_when_no_salary_mentioned():
    assert extract_salary("Buscamos QA Tester con experiencia en Selenium") is None
